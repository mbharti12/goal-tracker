import { NavLink } from "react-router-dom";
import { useNotifications } from "../context/NotificationsContext";

export const TAB_ITEMS = [
  { label: "Today", path: "/today" },
  { label: "Goals", path: "/goals" },
  { label: "Calendar", path: "/calendar" },
  { label: "Review", path: "/review" },
  { label: "Notifications", path: "/notifications" },
];

const BellIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      d="M12 4a5 5 0 0 0-5 5v3.5L5.4 15h13.2L17 12.5V9a5 5 0 0 0-5-5Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M9.8 17a2.2 2.2 0 0 0 4.4 0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export default function BottomTabs() {
  const { notifications } = useNotifications();
  const unreadCount = notifications.length;
  const badgeLabel = unreadCount > 99 ? "99+" : String(unreadCount);

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
          {tab.path === "/notifications" ? (
            <span className="tab-link__content">
              <span className="tab-icon">
                <BellIcon />
                {unreadCount > 0 && <span className="tab-badge">{badgeLabel}</span>}
              </span>
              <span className="tab-label">{tab.label}</span>
            </span>
          ) : (
            <span className="tab-label">{tab.label}</span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
