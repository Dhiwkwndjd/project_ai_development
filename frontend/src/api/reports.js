import { api } from "./client";

function periodParams(dateFrom, dateTo) {
  const params = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  return params;
}

/** Сводка отчёта за период. */
export async function fetchReportSummary({ dateFrom = "", dateTo = "", signal } = {}) {
  const { data } = await api.get("/reports/summary/", {
    params: periodParams(dateFrom, dateTo),
    signal,
  });
  return data;
}

function filenameFrom(disposition, fallback) {
  const match = /filename="?([^";]+)"?/.exec(disposition || "");
  return match ? match[1] : fallback;
}

/** Скачать CSV (loans или books) с сохранением BOM от сервера. */
export async function downloadReportCsv(kind, { dateFrom = "", dateTo = "" } = {}) {
  const response = await api.get(`/reports/${kind}.csv`, {
    params: periodParams(dateFrom, dateTo),
    responseType: "blob",
  });
  const filename = filenameFrom(response.headers["content-disposition"], `${kind}.csv`);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return filename;
}
