"use client";
import { useMemo } from "react";
import { useF1Store } from "@/store/useF1Store";
import { StrategyDriver, StrategyStint } from "@/lib/api";

const ROW_H = 32;
const LABEL_W = 48;
const PAD = { top: 8, right: 16, bottom: 28, left: LABEL_W + 8 };

interface Props {
  width?: number;
}

export default function StrategyGantt({ width = 800 }: Props) {
  const { strategyData, selectedStrategyDrivers, highlightedDriver, setHighlightedDriver } = useF1Store();

  const drivers = useMemo(() => {
    if (!strategyData) return [];
    const all = strategyData.drivers;
    if (selectedStrategyDrivers.length === 0) return all;
    return all.filter((d) => selectedStrategyDrivers.includes(d.code));
  }, [strategyData, selectedStrategyDrivers]);

  if (!strategyData || drivers.length === 0) return null;

  const totalLaps = strategyData.total_laps;
  const chartW = width - PAD.left - PAD.right;
  const chartH = drivers.length * ROW_H;
  const svgH = chartH + PAD.top + PAD.bottom;

  // Lap number → x pixel
  const x = (lap: number) => (lap / totalLaps) * chartW;

  // Tick marks every 10 laps
  const ticks = Array.from(
    { length: Math.floor(totalLaps / 10) },
    (_, i) => (i + 1) * 10
  ).filter((t) => t <= totalLaps);

  return (
    <div className="gantt-card">
      <div className="chart-title">Stint Strategy — all drivers</div>
      <div style={{ overflowX: "auto" }}>
        <svg
          width={Math.max(width, 600)}
          height={svgH}
          style={{ display: "block", fontFamily: "var(--mono)" }}
        >
          <g transform={`translate(${PAD.left}, ${PAD.top})`}>

            {/* Grid lines + lap axis */}
            {ticks.map((lap) => (
              <g key={lap}>
                <line
                  x1={x(lap)} y1={0}
                  x2={x(lap)} y2={chartH}
                  stroke="rgba(255,255,255,0.05)" strokeWidth={1}
                />
                <text
                  x={x(lap)} y={chartH + 16}
                  textAnchor="middle" fontSize={9} fill="#555"
                >
                  {lap}
                </text>
              </g>
            ))}

            {/* Axis label */}
            <text x={chartW / 2} y={chartH + 26} textAnchor="middle" fontSize={9} fill="#444">
              Lap
            </text>

            {/* Driver rows */}
            {drivers.map((driver, rowIdx) => {
              const y = rowIdx * ROW_H;
              const isHighlighted = highlightedDriver === driver.code;
              const isDimmed = highlightedDriver !== null && !isHighlighted;

              return (
                <g
                  key={driver.code}
                  opacity={isDimmed ? 0.3 : 1}
                  style={{ cursor: "pointer", transition: "opacity 0.2s" }}
                  onMouseEnter={() => setHighlightedDriver(driver.code)}
                  onMouseLeave={() => setHighlightedDriver(null)}
                >
                  {/* Row background on hover */}
                  <rect
                    x={-PAD.left} y={y + 1}
                    width={chartW + PAD.left + PAD.right}
                    height={ROW_H - 2}
                    fill={isHighlighted ? "rgba(255,255,255,0.03)" : "transparent"}
                    rx={4}
                  />

                  {/* Driver label */}
                  <text
                    x={-8} y={y + ROW_H / 2 + 4}
                    textAnchor="end" fontSize={11} fontWeight="700"
                    fill={driver.team_color}
                  >
                    {driver.code}
                  </text>

                  {/* Finish position badge */}
                  <text
                    x={-PAD.left + 2} y={y + ROW_H / 2 + 4}
                    textAnchor="start" fontSize={9}
                    fill="rgba(255,255,255,0.25)"
                  >
                    P{driver.finish_position}
                  </text>

                  {/* Stint bars */}
                  {driver.stints.map((stint) => {
                    const barX = x(stint.start_lap - 1);
                    const barW = Math.max(x(stint.end_lap) - barX, 2);
                    const barY = y + 4;
                    const barH = ROW_H - 8;

                    return (
                      <g key={stint.stint_number}>
                        <rect
                          x={barX} y={barY}
                          width={barW} height={barH}
                          fill={stint.compound_color}
                          opacity={0.85}
                          rx={3}
                        />
                        {/* Compound letter if bar is wide enough */}
                        {barW > 20 && (
                          <text
                            x={barX + barW / 2} y={barY + barH / 2 + 4}
                            textAnchor="middle" fontSize={10} fontWeight="700"
                            fill={stint.compound === "HARD" ? "#111" : "#000"}
                          >
                            {stint.compound[0]}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Pit stop markers */}
                  {driver.pit_stops.map((stop) => (
                    <g key={stop.stop_number}>
                      <line
                        x1={x(stop.lap)} y1={y + 2}
                        x2={x(stop.lap)} y2={y + ROW_H - 2}
                        stroke="#fff" strokeWidth={1.5}
                        opacity={0.6}
                      />
                      {/* Triangle marker at top */}
                      <polygon
                        points={`${x(stop.lap)},${y + 2} ${x(stop.lap) - 3},${y - 3} ${x(stop.lap) + 3},${y - 3}`}
                        fill="#fff" opacity={0.5}
                      />
                    </g>
                  ))}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Compound legend */}
      <div className="gantt-legend">
        {[
          { label: "Soft",   color: "#FF3333" },
          { label: "Medium", color: "#FFD700" },
          { label: "Hard",   color: "#FFFFFF" },
          { label: "Inter",  color: "#39B54A" },
          { label: "Wet",    color: "#0067FF" },
        ].map(({ label, color }) => (
          <div key={label} className="gantt-legend-item">
            <span className="gantt-legend-dot" style={{ background: color }} />
            <span>{label}</span>
          </div>
        ))}
        <div className="gantt-legend-item">
          <span className="gantt-pit-line" />
          <span>Pit stop</span>
        </div>
      </div>
    </div>
  );
}