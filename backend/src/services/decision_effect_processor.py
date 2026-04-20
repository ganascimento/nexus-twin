from loguru import logger

from src.enums import OrderStatus, TruckStatus


class DecisionEffectProcessor:
    def __init__(
        self,
        session,
        order_repo,
        warehouse_service,
        factory_repo,
        truck_service,
        route_service,
        event_repo,
        truck_repo,
        warehouse_repo,
        store_repo,
        route_repo,
    ):
        self._session = session
        self._order_repo = order_repo
        self._warehouse_service = warehouse_service
        self._factory_repo = factory_repo
        self._truck_service = truck_service
        self._route_service = route_service
        self._event_repo = event_repo
        self._truck_repo = truck_repo
        self._warehouse_repo = warehouse_repo
        self._store_repo = store_repo
        self._route_repo = route_repo

        self._handlers = {
            ("store", "order_replenishment"): self._handle_order_replenishment,
            ("warehouse", "confirm_order"): self._handle_confirm_order,
            ("warehouse", "reject_order"): self._handle_reject_order,
            ("warehouse", "request_resupply"): self._handle_request_resupply,
            ("factory", "start_production"): self._handle_start_production,
            ("factory", "send_stock"): self._handle_send_stock,
            ("truck", "accept_contract"): self._handle_accept_contract,
            ("truck", "refuse_contract"): self._handle_refuse_contract,
            ("truck", "request_maintenance"): self._handle_request_maintenance,
            ("truck", "alert_breakdown"): self._handle_alert_breakdown,
            ("truck", "reroute"): self._handle_reroute,
            ("factory", "stop_production"): self._handle_stop_production,
        }

    async def process(self, entity_type, entity_id, action, payload, current_tick):
        if action == "hold":
            return

        handler = self._handlers.get((entity_type, action))
        if handler is None:
            logger.warning(
                "No handler for ({}, {}), skipping effect", entity_type, action
            )
            return

        savepoint = await self._session.begin_nested()
        try:
            await handler(entity_id, payload, current_tick)
        except Exception:
            await savepoint.rollback()
            logger.exception(
                "Effect handler failed for ({}, {}) entity={} — rolling back partial effects",
                entity_type,
                action,
                entity_id,
            )
        else:
            if savepoint.is_active:
                await savepoint.commit()

    # --- Store handlers ---

    async def _handle_order_replenishment(self, entity_id, payload, tick):
        material_id = payload["material_id"]
        target_id = payload["from_warehouse_id"]

        if await self._order_repo.has_active_order(entity_id, material_id, target_id):
            logger.info(
                "Skipping duplicate order_replenishment: store={} material={} warehouse={}",
                entity_id,
                material_id,
                target_id,
            )
            return

        await self._order_repo.create(
            {
                "requester_type": "store",
                "requester_id": entity_id,
                "target_type": "warehouse",
                "target_id": target_id,
                "material_id": material_id,
                "quantity_tons": payload["quantity_tons"],
                "status": "pending",
            }
        )

    # --- Warehouse handlers ---

    async def _handle_confirm_order(self, entity_id, payload, tick):
        order_id = payload["order_id"]
        eta_ticks = payload["eta_ticks"]

        await self._warehouse_service.confirm_order(order_id, eta_ticks)

        order = await self._order_repo.get_by_id(order_id)
        await self._dispatch_truck_for_order(order, entity_id, tick)

    async def _handle_reject_order(self, entity_id, payload, tick):
        await self._warehouse_service.reject_order(
            payload["order_id"],
            payload["reason"],
            retry_after_ticks=payload.get("retry_after_ticks"),
        )

    async def _handle_request_resupply(self, entity_id, payload, tick):
        material_id = payload["material_id"]
        target_id = payload["from_factory_id"]

        if await self._order_repo.has_active_order(entity_id, material_id, target_id):
            logger.info(
                "Skipping duplicate request_resupply: warehouse={} material={} factory={}",
                entity_id,
                material_id,
                target_id,
            )
            return

        await self._order_repo.create(
            {
                "requester_type": "warehouse",
                "requester_id": entity_id,
                "target_type": "factory",
                "target_id": target_id,
                "material_id": material_id,
                "quantity_tons": payload["quantity_tons"],
                "status": "pending",
            }
        )

    # --- Factory handlers ---

    async def _handle_start_production(self, entity_id, payload, tick):
        await self._factory_repo.update_production_rate(
            entity_id, payload["material_id"], payload["quantity_tons"]
        )

    async def _handle_send_stock(self, entity_id, payload, tick):
        material_id = payload["material_id"]
        destination_warehouse_id = payload["destination_warehouse_id"]
        quantity_tons = payload["quantity_tons"]

        existing = await self._order_repo.get_active_by_requester_target_material(
            destination_warehouse_id, entity_id, material_id
        )
        already_reserved = existing is not None and existing.status == "confirmed"

        if not already_reserved:
            reserved = await self._factory_repo.atomic_reserve_stock(
                entity_id, material_id, quantity_tons
            )
            if not reserved:
                logger.warning(
                    "Insufficient factory stock to reserve for send_stock: factory={} material={} qty={}",
                    entity_id, material_id, quantity_tons,
                )
                return

            if existing is None:
                await self._order_repo.create(
                    {
                        "requester_type": "warehouse",
                        "requester_id": destination_warehouse_id,
                        "target_type": "factory",
                        "target_id": entity_id,
                        "material_id": material_id,
                        "quantity_tons": quantity_tons,
                        "status": "confirmed",
                    }
                )
            else:
                await self._order_repo.update_status(existing.id, "confirmed")

        truck = await self._find_truck_for_factory(entity_id)
        if truck is None:
            logger.warning("No truck available for send_stock: factory={}", entity_id)
            return

        event_type = (
            "new_order" if truck.factory_id == entity_id else "contract_proposal"
        )
        await self._event_repo.create(
            {
                "event_type": event_type,
                "source": "decision_effect_processor",
                "entity_type": "truck",
                "entity_id": truck.id,
                "payload": {
                    "material_id": material_id,
                    "quantity_tons": payload["quantity_tons"],
                    "origin_type": "factory",
                    "origin_id": entity_id,
                    "destination_type": "warehouse",
                    "destination_id": destination_warehouse_id,
                },
                "status": "active",
                "tick_start": tick,
            }
        )

    # --- Truck handlers ---

    async def _handle_accept_contract(self, entity_id, payload, tick):
        truck = await self._truck_repo.get_by_id(entity_id)
        order = await self._order_repo.get_by_id(payload["order_id"])

        if truck is not None and truck.status in (
            TruckStatus.BROKEN.value,
            TruckStatus.MAINTENANCE.value,
        ):
            logger.warning(
                "Ignoring accept_contract: truck={} status={}",
                entity_id,
                truck.status,
            )
            return

        if order is None or order.status in (
            OrderStatus.DELIVERED.value,
            OrderStatus.CANCELLED.value,
        ):
            logger.warning(
                "Ignoring accept_contract: order={} status={}",
                payload.get("order_id"),
                getattr(order, "status", None),
            )
            return

        origin_coords = await self._get_entity_coords(
            order.target_type, order.target_id
        )
        dest_coords = await self._get_entity_coords(
            order.requester_type, order.requester_id
        )

        route_data = await self._route_service.compute_route(
            origin_coords[0],
            origin_coords[1],
            dest_coords[0],
            dest_coords[1],
            tick,
        )
        route_data["order_id"] = str(order.id)

        route = await self._route_service.create_route(
            entity_id,
            order.target_type,
            order.target_id,
            order.requester_type,
            order.requester_id,
            route_data,
        )

        cargo = {
            "order_id": str(order.id),
            "material_id": order.material_id,
            "quantity_tons": order.quantity_tons,
            "origin_type": order.target_type,
            "origin_id": order.target_id,
            "destination_type": order.requester_type,
            "destination_id": order.requester_id,
        }
        await self._truck_service.assign_route(entity_id, str(route.id), cargo)

    async def _handle_refuse_contract(self, entity_id, payload, tick):
        order = await self._order_repo.get_by_id(payload["order_id"])

        next_truck = await self._find_idle_third_party_truck(exclude_id=entity_id)
        if next_truck is None:
            logger.warning(
                "No alternative truck for refused contract: order={}",
                payload["order_id"],
            )
            return

        await self._event_repo.create(
            {
                "event_type": "contract_proposal",
                "source": "decision_effect_processor",
                "entity_type": "truck",
                "entity_id": next_truck.id,
                "payload": {
                    "order_id": str(order.id),
                    "origin_type": order.target_type,
                    "origin_id": order.target_id,
                    "destination_type": order.requester_type,
                    "destination_id": order.requester_id,
                },
                "status": "active",
                "tick_start": tick,
            }
        )

    async def _handle_request_maintenance(self, entity_id, payload, tick):
        await self._truck_service.schedule_maintenance(entity_id, current_tick=tick)

    async def _handle_alert_breakdown(self, entity_id, payload, tick):
        broken_truck = await self._truck_repo.get_by_id(entity_id)
        route = await self._route_repo.get_active_by_truck(entity_id)

        rescue_truck = await self._find_idle_third_party_truck(exclude_id=entity_id)
        if rescue_truck is None:
            logger.warning(
                "No rescue truck available for broken truck={}", entity_id
            )
            return

        event_payload = {"rescue_for": entity_id}
        if route:
            event_payload["order_id"] = str(route.order_id) if route.order_id else None
            event_payload["origin_type"] = route.origin_type
            event_payload["origin_id"] = route.origin_id
            event_payload["destination_type"] = route.dest_type
            event_payload["destination_id"] = route.dest_id
        cargo = broken_truck.cargo if broken_truck else None
        if cargo is not None:
            if isinstance(cargo, dict):
                event_payload["material_id"] = cargo.get("material_id")
                event_payload["quantity_tons"] = cargo.get("quantity_tons")
            else:
                event_payload["material_id"] = getattr(cargo, "material_id", None)
                event_payload["quantity_tons"] = getattr(cargo, "quantity_tons", None)

        await self._event_repo.create({
            "event_type": "contract_proposal",
            "source": "decision_effect_processor",
            "entity_type": "truck",
            "entity_id": rescue_truck.id,
            "payload": event_payload,
            "status": "active",
            "tick_start": tick,
        })

    async def _handle_reroute(self, entity_id, payload, tick):
        truck = await self._truck_repo.get_by_id(entity_id)
        if truck is None:
            logger.warning("No truck for reroute: truck={}", entity_id)
            return
        route = await self._route_repo.get_active_by_truck(entity_id)
        if route is None:
            logger.warning("No active route for reroute: truck={}", entity_id)
            return

        dest_coords = await self._get_entity_coords(route.dest_type, route.dest_id)

        route_data = await self._route_service.compute_route(
            truck.current_lat, truck.current_lng,
            dest_coords[0], dest_coords[1],
            tick,
        )

        await self._route_repo.update_route_data(
            route.id,
            route_data["path"],
            route_data["timestamps"],
            route_data["eta_ticks"],
        )

    async def _handle_stop_production(self, entity_id, payload, tick):
        material_id = payload.get("material_id")
        if material_id:
            await self._factory_repo.update_production_rate(entity_id, material_id, 0.0)

    # --- Helpers ---

    async def _dispatch_truck_for_order(self, order, warehouse_id, tick):
        truck = await self._find_idle_third_party_truck()
        if truck is None:
            logger.warning(
                "No truck available for confirmed order: warehouse={}", warehouse_id
            )
            return

        await self._event_repo.create(
            {
                "event_type": "contract_proposal",
                "source": "decision_effect_processor",
                "entity_type": "truck",
                "entity_id": truck.id,
                "payload": {
                    "order_id": str(order.id),
                    "origin_type": order.target_type,
                    "origin_id": order.target_id,
                    "destination_type": order.requester_type,
                    "destination_id": order.requester_id,
                },
                "status": "active",
                "tick_start": tick,
            }
        )

    async def _find_truck_for_factory(self, factory_id):
        factory_trucks = await self._truck_repo.get_by_factory(factory_id)
        for t in factory_trucks:
            if t.status == "idle":
                return t

        return await self._find_idle_third_party_truck()

    async def _find_idle_third_party_truck(self, exclude_id=None):
        all_trucks = await self._truck_repo.get_all()
        for t in all_trucks:
            if t.status == "idle" and t.truck_type == "terceiro" and t.id != exclude_id:
                return t
        return None

    async def _get_entity_coords(self, entity_type, entity_id):
        if entity_type == "warehouse":
            entity = await self._warehouse_repo.get_by_id(entity_id)
            return (entity.lat, entity.lng)
        elif entity_type == "store":
            entity = await self._store_repo.get_by_id(entity_id)
            return (entity.lat, entity.lng)
        elif entity_type == "factory":
            entity = await self._factory_repo.get_by_id(entity_id)
            return (entity.lat, entity.lng)
        raise ValueError(f"Unknown entity type for coords: {entity_type}")
