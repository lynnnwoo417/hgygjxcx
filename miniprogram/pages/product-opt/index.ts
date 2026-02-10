// pages/product-opt/index.ts
const SUB_KEY = 'my_subscriptions';
const REMINDER_KEY = 'my_reminders';

function loadComebacks(): any[] {
  try {
    const list = require('../../data/comebacks.js') as any[];
    return Array.isArray(list) ? list : [];
  } catch (_) {
    return [];
  }
}

function normalizeText(s: string): string {
  return (s || '').trim().toLowerCase();
}

Page({
  data: {
    input: '' as string,
    subs: [] as string[],
    hint: '' as string
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    let subs: string[] = [];
    try {
      const v = wx.getStorageSync(SUB_KEY);
      subs = Array.isArray(v) ? v : [];
    } catch (_) {}
    this.setData({ subs });
    this.updateReminders(subs);
  },

  onInput(e: WechatMiniprogram.Input) {
    const value = e && e.detail && typeof e.detail.value === 'string' ? e.detail.value : '';
    this.setData({ input: value });
  },

  onAdd() {
    const raw = (this.data.input || '').trim();
    if (!raw) {
      wx.showToast({ title: '请输入团体名', icon: 'none' });
      return;
    }
    let subs: string[] = [];
    try {
      const v = wx.getStorageSync(SUB_KEY);
      subs = Array.isArray(v) ? v : [];
    } catch (_) {}
    const exists = subs.some(s => normalizeText(s) === normalizeText(raw));
    if (!exists) subs.unshift(raw);
    try {
      wx.setStorageSync(SUB_KEY, subs.slice(0, 60));
    } catch (_) {}
    this.setData({ input: '' });
    this.refresh();
  },

  onRemove(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    let subs: string[] = [];
    try {
      const v = wx.getStorageSync(SUB_KEY);
      subs = Array.isArray(v) ? v : [];
    } catch (_) {}
    subs.splice(index, 1);
    try {
      wx.setStorageSync(SUB_KEY, subs);
    } catch (_) {}
    this.refresh();
  },

  updateReminders(subs: string[]) {
    const normalizedSubs = subs.map(s => normalizeText(s)).filter(Boolean);
    const comebacks = loadComebacks();
    if (normalizedSubs.length === 0) {
      try { wx.setStorageSync(REMINDER_KEY, []); } catch (_) {}
      this.setData({ hint: '还没有订阅任何团体' });
      return;
    }

    const today = new Date();
    const start = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    const end = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000);

    const toDate = (dk: string) => {
      if (!dk || !/^\d{4}-\d{2}-\d{2}$/.test(dk)) return null;
      const d = new Date(dk + 'T00:00:00');
      return isNaN(d.getTime()) ? null : d;
    };

    const matched: any[] = [];
    for (let i = 0; i < comebacks.length; i++) {
      const it = comebacks[i];
      const artist = normalizeText(it.artist || '');
      if (!artist) continue;
      const hit = normalizedSubs.some(s => artist.indexOf(s) >= 0);
      if (!hit) continue;
      const d = toDate(it.dateKey || '');
      if (!d) continue;
      if (d < start || d > end) continue;
      matched.push(it);
    }

    matched.sort((a, b) => String(b.dateKey || '').localeCompare(String(a.dateKey || '')));
    try {
      wx.setStorageSync(REMINDER_KEY, matched);
    } catch (_) {}

    const hint = matched.length > 0 ? `最近有 ${matched.length} 条回归提醒` : '最近暂无回归提醒';
    this.setData({ hint });
  }
});

