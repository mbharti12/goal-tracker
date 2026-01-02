import { NavLink } from "react-router-dom";

export const TAB_ITEMS = [
  { label: "Today", path: "/today" },
  { label: "Goals", path: "/goals" },
  { label: "Calendar", path: "/calendar" },
  { label: "Review", path: "/review" },
];

export default function BottomTabs() {
  return (
    <nav className="bottom-tabs" aria-label="Primary">
      {TAB_ITEMS.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          className={({ isActive }) =>
            `tab-link${isActive ? " tab-link--active" : ""}`
          }
        >
          <span className="tab-label">{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
