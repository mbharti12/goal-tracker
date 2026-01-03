import { useCallback, useMemo, useState } from "react";
import { getErrorMessage } from "../api/client";
import { markNotificationRead } from "../api/endpoints";
import type { NotificationRead } from "../api/types";
import { useNotifications } from "../context/NotificationsContext";

const formatUnknownDate = "Unknown time";

export default function Notifications() {
  const { notifications, loading, error, reload, setNotifications } = useNotifications();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set());

  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }),
    [],
  );

  const unreadCount = notifications.length;

  const formatTimestamp = useCallback(
    (value: string) => {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return formatUnknownDate;
      }
      return dateFormatter.format(date);
    },
    [dateFormatter],
  );

  const handleMarkRead = useCallback(
    async (notification: NotificationRead) => {
      if (pendingIds.has(notification.id)) {
        return;
      }
      setActionError(null);
      setPendingIds((prev) => new Set(prev).add(notification.id));
      try {
        await markNotificationRead(notification.id);
        setNotifications((prev) => prev.filter((item) => item.id !== notification.id));
      } catch (errorValue) {
        setActionError(getErrorMessage(errorValue));
      } finally {
        setPendingIds((prev) => {
          const next = new Set(prev);
          next.delete(notification.id);
          return next;
        });
      }
    },
    [pendingIds, setNotifications],
  );

  const handleRetry = useCallback(() => {
    setActionError(null);
    void reload();
  }, [reload]);

  return (
    <section className="page notifications-page">
      <div className="card">
        <div className="notifications-header">
          <div>
            <h2>Notifications</h2>
            <p>Unread reminders and updates.</p>
          </div>
          <div className="notifications-count">{unreadCount} unread</div>
        </div>

        {actionError && (
          <div className="status status--error" role="alert">
            Could not mark notification as read. {actionError}
          </div>
        )}

        {loading ? (
          <div className="status status--loading">Loading notifications...</div>
        ) : error ? (
          <div className="status status--error" role="alert">
            <div>Could not load notifications. {error}</div>
            <button className="action-button" type="button" onClick={handleRetry}>
              Retry
            </button>
          </div>
        ) : unreadCount === 0 ? (
          <div className="empty-state">No unread notifications.</div>
        ) : (
          <div className="notifications-list">
            {notifications.map((notification) => {
              const isPending = pendingIds.has(notification.id);
              return (
                <button
                  key={notification.id}
                  type="button"
                  className={`notification-card${isPending ? " notification-card--pending" : ""}`}
                  onClick={() => void handleMarkRead(notification)}
                  disabled={isPending}
                >
                  <div className="notification-card__header">
                    <div className="notification-card__title">{notification.title}</div>
                    <div className="notification-card__date">
                      {formatTimestamp(notification.created_at)}
                    </div>
                  </div>
                  <div className="notification-card__body">{notification.body}</div>
                  <div className="notification-card__hint">Tap to mark as read</div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
