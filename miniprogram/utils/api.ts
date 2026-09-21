/**
 * 小程序只通过这里访问活动 API。
 * 密钥不会出现在前端。SCHEDULE_API_BASE 为空时，调用方应走本地 data/*.js。
 */
import { SCHEDULE_API_BASE } from './config';

export type RemoteSchedule = {
  id: number;
  artist: string;
  type: string;
  date: string;
  dateKey: string;
  detail: string;
  ticketPlatform?: string;
  ticketTime?: string;
  venue?: string;
  showTime?: string;
  detailUrl?: string;
  officialUrl?: string;
  locationText?: string;
  coverImage?: string;
  region?: string;
  sourceEventId?: string;
};

function baseUrl(): string {
  return (SCHEDULE_API_BASE || '').replace(/\/$/, '');
}

export function hasRemoteApi(): boolean {
  return !!baseUrl();
}

function request<T>(path: string): Promise<T> {
  const root = baseUrl();
  if (!root) {
    return Promise.reject(new Error('no api'));
  }
  return new Promise((resolve, reject) => {
    wx.request({
      url: root + path,
      method: 'GET',
      timeout: 20000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T);
          return;
        }
        reject(new Error('http ' + res.statusCode));
      },
      fail: (err) => reject(err)
    });
  });
}

export function getEvents(params?: {
  start_date?: string;
  end_date?: string;
  event_type?: string;
  artist?: string;
  status?: string;
}): Promise<RemoteSchedule[]> {
  const q: string[] = [];
  if (params) {
    Object.keys(params).forEach((key) => {
      const val = (params as Record<string, string | undefined>)[key];
      if (val) q.push(encodeURIComponent(key) + '=' + encodeURIComponent(val));
    });
  }
  const suffix = q.length ? '?' + q.join('&') : '';
  return request<{ schedules?: RemoteSchedule[] }>('/api/events' + suffix).then(
    (data) => (Array.isArray(data.schedules) ? data.schedules : [])
  );
}

export function searchEvents(q: string): Promise<RemoteSchedule[]> {
  const query = (q || '').trim();
  if (!query) return Promise.resolve([]);
  return request<{ schedules?: RemoteSchedule[] }>(
    '/api/events/search?q=' + encodeURIComponent(query)
  ).then((data) => (Array.isArray(data.schedules) ? data.schedules : []));
}

export function getEventDetail(id: number | string): Promise<RemoteSchedule | null> {
  if (id === '' || id === undefined || id === null) return Promise.resolve(null);
  return request<{ event?: RemoteSchedule }>('/api/events/' + encodeURIComponent(String(id))).then(
    (data) => data.event || null
  );
}

export function getCalendarEvents(
  year: number,
  month: number
): Promise<{ dates: string[]; schedules: RemoteSchedule[] }> {
  return request<{ dates?: string[]; schedules?: RemoteSchedule[] }>(
    '/api/events/calendar?year=' + year + '&month=' + month
  ).then((data) => ({
    dates: Array.isArray(data.dates) ? data.dates : [],
    schedules: Array.isArray(data.schedules) ? data.schedules : []
  }));
}
