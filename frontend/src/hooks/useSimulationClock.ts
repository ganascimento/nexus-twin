import { useEffect, useRef, useState } from "react";

export function useSimulationClock(): number {
  const [now, setNow] = useState<number>(() => Date.now());
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const loop = () => {
      setNow(Date.now());
      frameRef.current = requestAnimationFrame(loop);
    };
    frameRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frameRef.current);
  }, []);

  return now;
}
