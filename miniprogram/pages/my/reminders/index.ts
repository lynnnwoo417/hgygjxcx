// pages/my/reminders/index.ts
const KEY = 'my_reminders';

Page({
  data: {
    items: [] as any[],
    notice: '' as string
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    let items: any[] = [];
    try {
      const v = wx.getStorageSync(KEY);
      items = Array.isArray(v) ? v : [];
    } catch (_) {}
    // 最新在前
    items = items.slice().sort((a, b) => String(b.dateKey || '').localeCompare(String(a.dateKey || '')));
    const notice = items.length > 0 ? `发现 ${items.length} 条回归提醒` : '';
    this.setData({ items, notice });
  }
});

