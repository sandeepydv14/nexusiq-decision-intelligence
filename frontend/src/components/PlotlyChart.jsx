import React, { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

export default function PlotlyChart({ data, layout = {}, height = 340, theme = "light" }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !data || !data.length) return;

    const isDark = theme === "dark";
    const mergedLayout = {
      autosize: true,
      height,
      margin: { t: layout.title ? 40 : 18, r: 18, b: 48, l: 56, ...(layout.margin || {}) },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: {
        family: "Inter, sans-serif",
        size: 12,
        color: isDark ? "#cbd5e1" : "#334155",
      },
      xaxis: {
        gridcolor: isDark ? "#1f2937" : "#e2e8f0",
        zerolinecolor: isDark ? "#374151" : "#cbd5e1",
        ...(layout.xaxis || {}),
      },
      yaxis: {
        gridcolor: isDark ? "#1f2937" : "#e2e8f0",
        zerolinecolor: isDark ? "#374151" : "#cbd5e1",
        ...(layout.yaxis || {}),
      },
      legend: {
        orientation: "h",
        y: -0.22,
        ...(layout.legend || {}),
      },
      ...layout,
    };

    // Preserve merged axis grids if layout passed custom xaxis/yaxis
    mergedLayout.xaxis = {
      gridcolor: isDark ? "#1f2937" : "#e2e8f0",
      zerolinecolor: isDark ? "#374151" : "#cbd5e1",
      ...(layout.xaxis || {}),
    };
    mergedLayout.yaxis = {
      gridcolor: isDark ? "#1f2937" : "#e2e8f0",
      zerolinecolor: isDark ? "#374151" : "#cbd5e1",
      ...(layout.yaxis || {}),
    };

    Plotly.react(el, data, mergedLayout, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });

    const observer = new ResizeObserver(() => {
      if (el) Plotly.Plots.resize(el);
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      Plotly.purge(el);
    };
  }, [data, layout, height, theme]);

  return <div ref={containerRef} style={{ width: "100%", minHeight: height }} />;
}
