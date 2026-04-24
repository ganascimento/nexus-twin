import { useEffect, useState } from "react";
import { useMap } from "react-map-gl/maplibre";

export function useMapZoom(fallback = 7): number {
  const { current } = useMap();
  const [zoom, setZoom] = useState<number>(() =>
    current?.getMap().getZoom() ?? fallback,
  );

  useEffect(() => {
    const map = current?.getMap();
    if (!map) return;
    const handler = () => setZoom(map.getZoom());
    handler();
    map.on("zoom", handler);
    return () => {
      map.off("zoom", handler);
    };
  }, [current]);

  return zoom;
}
