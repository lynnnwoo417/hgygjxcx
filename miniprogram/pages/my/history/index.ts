// pages/my/history/index.ts
const KEY = 'my_history';

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
    this.setData({ items });
  },

  onOpen(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const item = (this.data.items || [])[index];
    if (!item) return;
    const app = getApp<IAppOption>();
    app.globalData.eventDetail = item;
    wx.navigateTo({ url: '/pages/event-detail/index' });
  },

  onClear() {
    wx.showModal({
      title: '清空历史',
      content: '确认清空本机历史记录？',
      confirmText: '清空',
      success: (res) => {
        if (!res.confirm) return;
        try {
          wx.removeStorageSync(KEY);
        } catch (_) {}
        this.refresh();
        wx.showToast({ title: '已清空', icon: 'none' });
      }
    });
  }
});

