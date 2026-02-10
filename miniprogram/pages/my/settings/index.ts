// pages/my/settings/index.ts
Page({
  data: {
    storageInfo: '' as string
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    let storageInfo = '';
    try {
      const info = wx.getStorageInfoSync();
      storageInfo = `${info.currentSize}KB / ${info.limitSize}KB`;
    } catch (_) {}
    this.setData({ storageInfo });
  },

  onClearCache() {
    wx.showModal({
      title: '清理缓存',
      content: '将清理小程序 storage（但会尽量保留收藏/提醒/历史/资料）。确认继续？',
      confirmText: '清理',
      success: (res) => {
        if (!res.confirm) return;
        try {
          // 先备份我们自己的 key
          const keepKeys = ['my_profile', 'my_favorites', 'my_reminders', 'my_history'];
          const keep: any = {};
          for (let i = 0; i < keepKeys.length; i++) {
            const k = keepKeys[i];
            keep[k] = wx.getStorageSync(k);
          }
          wx.clearStorageSync();
          for (let i = 0; i < keepKeys.length; i++) {
            const k = keepKeys[i];
            if (typeof keep[k] !== 'undefined') wx.setStorageSync(k, keep[k]);
          }
        } catch (_) {}
        this.refresh();
        wx.showToast({ title: '已清理', icon: 'none' });
      }
    });
  }
});

