import { useEffect, useState } from "react";

export function useAnimatedCurrentTime(): number {
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  useEffect(() => {
    let frameId = 0;
    const tick = () => {
      setCurrentTime(Date.now());
      frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, []);

  return currentTime;
}
