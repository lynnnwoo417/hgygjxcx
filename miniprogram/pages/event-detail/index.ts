// pages/event-detail/index.ts
Page({
  data: {
    artist: '',
    type: '',
    date: '',
    dateKey: '',
    detail: '',
    ticketPlatform: '' as string | undefined,
    ticketTime: '' as string | undefined,
    showTime: '' as string | undefined,
    detailUrl: '' as string | undefined,
    locationText: '' as string | undefined,
    coverImage: '' as string | undefined,
    isFavorite: false as boolean,
    posterExpand: false as boolean
  },

  onLoad() {
    const app = getApp<IAppOption>();
    const detail = app.globalData.eventDetail;
    if (!detail) {
      wx.showToast({ title: '暂无详情', icon: 'none' });
      return;
    }
    const payload = {
      artist: detail.artist,
      type: detail.type,
      date: detail.date,
      dateKey: detail.dateKey,
      detail: detail.detail,
      ticketPlatform: detail.ticketPlatform,
      ticketTime: detail.ticketTime,
      showTime: detail.showTime,
      detailUrl: detail.detailUrl,
      locationText: (detail as any).locationText,
      coverImage: (detail as any).coverImage
    };
    this.setData(payload);

    // 写入“历史”（本机存储）
    this.saveToHistory(payload);
    // 同步收藏状态
    this.refreshFavorite(payload);
  },

  makeKey(item: any) {
    return `${item.detailUrl || ''}|${item.dateKey || ''}|${item.type || ''}|${item.artist || ''}|${item.detail || ''}`;
  },

  saveToHistory(item: any) {
    const KEY = 'my_history';
    try {
      const list = wx.getStorageSync(KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const next = [item];
      for (let i = 0; i < arr.length; i++) {
        const it = arr[i];
        if (this.makeKey(it) === key) continue;
        next.push(it);
        if (next.length >= 120) break;
      }
      wx.setStorageSync(KEY, next);
    } catch (_) {}
  },

  refreshFavorite(item: any) {
    const KEY = 'my_favorites';
    try {
      const list = wx.getStorageSync(KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const hit = arr.some((it: any) => this.makeKey(it) === key);
      this.setData({ isFavorite: hit });
    } catch (_) {
      this.setData({ isFavorite: false });
    }
  },

  onToggleFavorite() {
    const KEY = 'my_favorites';
    const item = {
      id: 0,
      artist: this.data.artist,
      type: this.data.type,
      date: this.data.date,
      dateKey: this.data.dateKey,
      detail: this.data.detail,
      ticketPlatform: this.data.ticketPlatform,
      ticketTime: this.data.ticketTime,
      showTime: this.data.showTime,
      detailUrl: this.data.detailUrl,
      locationText: this.data.locationText,
      coverImage: this.data.coverImage
    };

    try {
      const list = wx.getStorageSync(KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const exists = arr.some((it: any) => this.makeKey(it) === key);
      let next: any[] = [];
      if (exists) {
        next = arr.filter((it: any) => this.makeKey(it) !== key);
        wx.setStorageSync(KEY, next);
        this.setData({ isFavorite: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
      } else {
        next = [item].concat(arr);
        if (next.length > 200) next = next.slice(0, 200);
        wx.setStorageSync(KEY, next);
        this.setData({ isFavorite: true });
        wx.showToast({ title: '已加入收藏', icon: 'none' });
      }
    } catch (_) {
      wx.showToast({ title: '收藏失败', icon: 'none' });
    }
  },

  onOpenLink() {
    const url = this.data.detailUrl;
    if (!url) {
      wx.showToast({ title: '暂无链接', icon: 'none' });
      return;
    }
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '链接已复制' })
    });
  },

  onExpandPoster() {
    if (this.data.coverImage) {
      this.setData({ posterExpand: true });
    }
  },

  onClosePosterExpand() {
    this.setData({ posterExpand: false });
  },

  onSavePoster() {
    const url = this.data.coverImage;
    if (!url) {
      wx.showToast({ title: '暂无海报', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '保存中…' });
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode !== 200) {
          wx.hideLoading();
          wx.showToast({ title: '下载失败', icon: 'none' });
          return;
        }
        wx.saveImageToPhotosAlbum({
          filePath: res.tempFilePath,
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: '已保存到相册' });
          },
          fail: (err) => {
            wx.hideLoading();
            if (err.errMsg && err.errMsg.indexOf('auth') !== -1) {
              wx.showModal({
                title: '需要相册权限',
                content: '请允许保存图片到相册',
                confirmText: '去设置',
                success: (m) => {
                  if (m.confirm) {
                    wx.openSetting();
                  }
                }
              });
            } else {
              wx.showToast({ title: '保存失败', icon: 'none' });
            }
          }
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '下载失败', icon: 'none' });
      }
    });
  }
});
