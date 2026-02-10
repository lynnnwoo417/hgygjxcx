// pages/my/favorites/index.ts
const KEY = 'my_favorites';

Page({
  data: {
    items: [] as any[]
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
    this.setData({ items });
  },

  onOpen(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const item = (this.data.items || [])[index];
    if (!item) return;
    const app = getApp<IAppOption>();
    app.globalData.eventDetail = item;
    wx.navigateTo({ url: '/pages/event-detail/index' });
  }
});

