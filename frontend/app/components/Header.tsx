import React from "react";

interface HeaderProps {
  title?: string;
  subtitle?: string;
  bgColor?: string;
}

const Header = ({ 
  title = "Startup Sourcing Overview",
  subtitle = "Combined totals across all GCED cycles",
  bgColor = "#8B1E2F"
}: HeaderProps) => (
  <div 
    className="text-white px-6 py-4 rounded-t-lg"
    style={{ backgroundColor: bgColor }}
  >
    <h2 className="text-xl font-semibold">{title}</h2>
    {subtitle && (
      <p className="text-sm opacity-80">
        {subtitle}
      </p>
    )}
  </div>
);

export default Header;