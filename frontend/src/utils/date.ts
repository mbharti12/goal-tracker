export const formatDateInput = (date: Date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export const parseDateInput = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
};

export const addDays = (value: string, delta: number) => {
  const date = parseDateInput(value);
  date.setDate(date.getDate() + delta);
  return formatDateInput(date);
};

export const startOfWeek = (value: Date, weekStartsOn = 1) => {
  const date = new Date(value);
  const day = date.getDay();
  const diff = (day - weekStartsOn + 7) % 7;
  date.setDate(date.getDate() - diff);
  return date;
};

export const endOfWeek = (value: Date, weekStartsOn = 1) => {
  const date = new Date(value);
  const day = date.getDay();
  const diff = (weekStartsOn + 6 - day + 7) % 7;
  date.setDate(date.getDate() + diff);
  return date;
};

export const listDateRange = (start: string, end: string) => {
  const dates: string[] = [];
  const cursor = parseDateInput(start);
  const endDate = parseDateInput(end);
  while (cursor <= endDate) {
    dates.push(formatDateInput(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
};
