// pages/event-detail/index.ts
import { getEventDetail, hasRemoteApi } from '../../utils/api';

const FAVORITES_KEY = 'my_favorites';
const RECORDS_KEY = 'my_records';

function looksLikeClockOrSaleTime(text: string): boolean {
  const s = (text || '').trim();
  if (!s) return false;
  return (
    /^\d{1,2}:\d{2}/.test(s) ||
    /\d{1,2}:\d{2}\s*(kst|jst|cst|sgt)/i.test(s) ||
    /(开票|预售|onsale|on sale|ticket time)/i.test(s)
  );
}

function splitTicketAndVenue(item: {
  ticketTime?: string;
  venue?: string;
  locationText?: string;
}): { ticketTime?: string; venue?: string; locationText?: string } {
  const locationText = (item.locationText || '').trim();
  let ticketTime = (item.ticketTime || '').trim();
  let venue = (item.venue || '').trim();
  if (ticketTime === '해당 없음' || ticketTime === '-' || ticketTime === 'N/A') {
    ticketTime = '';
  }
  if (!venue && ticketTime && !looksLikeClockOrSaleTime(ticketTime)) {
    venue = ticketTime;
    ticketTime = '';
  }
  return {
    ticketTime: ticketTime || undefined,
    venue: venue || undefined,
    locationText: locationText || undefined
  };
}

function officialCtaText(type: string): string {
  if (type === '签售') return '前往报名';
  if (type === '演唱会') return '前往购票';
  if (type === '活动') return '查看官方公告';
  return '查看官方公告';
}

Page({
  data: {
    artist: '',
    type: '',
    date: '',
    dateKey: '',
    detail: '',
    ticketPlatform: '' as string | undefined,
    ticketTime: '' as string | undefined,
    venue: '' as string | undefined,
    showTime: '' as string | undefined,
    detailUrl: '' as string | undefined,
    officialUrl: '' as string | undefined,
    locationText: '' as string | undefined,
    coverImage: '' as string | undefined,
    isFavorite: false as boolean,
    isRecorded: false as boolean,
    ctaText: '查看官方公告',
    posterExpand: false as boolean
  },

  onLoad() {
    const app = getApp<IAppOption>();
    const detail = app.globalData.eventDetail;
    if (!detail) {
      wx.showToast({ title: '暂无详情', icon: 'none' });
      return;
    }
    const split = splitTicketAndVenue(detail as any);
    const payload = {
      artist: detail.artist,
      type: detail.type,
      date: detail.date,
      dateKey: detail.dateKey,
      detail: detail.detail,
      ticketPlatform: detail.ticketPlatform,
      ticketTime: split.ticketTime,
      venue: split.venue,
      showTime: detail.showTime,
      detailUrl: detail.detailUrl,
      officialUrl: (detail as any).officialUrl,
      locationText: split.locationText,
      coverImage: (detail as any).coverImage,
      ctaText: officialCtaText(detail.type)
    };
    this.setData(payload);

    this.saveToHistory(payload);
    this.refreshFavorite(payload);
    this.refreshRecorded(payload);

    if (hasRemoteApi() && detail.id) {
      getEventDetail(detail.id)
        .then((remote) => {
          if (!remote) return;
          const splitRemote = splitTicketAndVenue(remote as any);
          this.setData({
            artist: remote.artist || this.data.artist,
            type: remote.type || this.data.type,
            date: remote.date || this.data.date,
            dateKey: remote.dateKey || this.data.dateKey,
            detail: remote.detail || this.data.detail,
            ticketPlatform: remote.ticketPlatform || this.data.ticketPlatform,
            ticketTime: splitRemote.ticketTime || this.data.ticketTime,
            venue: splitRemote.venue || this.data.venue,
            showTime: remote.showTime || this.data.showTime,
            detailUrl: remote.detailUrl || this.data.detailUrl,
            officialUrl: remote.officialUrl || this.data.officialUrl,
            locationText: splitRemote.locationText || this.data.locationText,
            coverImage: remote.coverImage || this.data.coverImage,
            ctaText: officialCtaText(remote.type || this.data.type)
          });
        })
        .catch(() => {
          /* 保留页面传入的详情 */
        });
    }
  },

  makeKey(item: any) {
    return `${item.detailUrl || ''}|${item.dateKey || ''}|${item.type || ''}|${item.artist || ''}|${item.detail || ''}`;
  },

  currentItem() {
    return {
      id: 0,
      artist: this.data.artist,
      type: this.data.type,
      date: this.data.date,
      dateKey: this.data.dateKey,
      detail: this.data.detail,
      ticketPlatform: this.data.ticketPlatform,
      ticketTime: this.data.ticketTime,
      venue: this.data.venue,
      showTime: this.data.showTime,
      detailUrl: this.data.detailUrl,
      officialUrl: this.data.officialUrl,
      locationText: this.data.locationText,
      coverImage: this.data.coverImage
    };
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
    try {
      const list = wx.getStorageSync(FAVORITES_KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const hit = arr.some((it: any) => this.makeKey(it) === key);
      this.setData({ isFavorite: hit });
    } catch (_) {
      this.setData({ isFavorite: false });
    }
  },

  refreshRecorded(item: any) {
    try {
      const list = wx.getStorageSync(RECORDS_KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const hit = arr.some((it: any) => this.makeKey(it) === key);
      this.setData({ isRecorded: hit });
    } catch (_) {
      this.setData({ isRecorded: false });
    }
  },

  onToggleFavorite() {
    const item = this.currentItem();
    try {
      const list = wx.getStorageSync(FAVORITES_KEY);
      const arr = Array.isArray(list) ? list : [];
      const key = this.makeKey(item);
      const exists = arr.some((it: any) => this.makeKey(it) === key);
      let next: any[] = [];
      if (exists) {
        next = arr.filter((it: any) => this.makeKey(it) !== key);
        wx.setStorageSync(FAVORITES_KEY, next);
        this.setData({ isFavorite: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
      } else {
        next = [item].concat(arr);
        if (next.length > 200) next = next.slice(0, 200);
        wx.setStorageSync(FAVORITES_KEY, next);
        this.setData({ isFavorite: true });
        wx.showToast({ title: '已加入收藏', icon: 'none' });
      }
    } catch (_) {
      wx.showToast({ title: '收藏失败', icon: 'none' });
    }
  },

  onToggleTrip() {
    const item = this.currentItem();
    const key = this.makeKey(item);
    let records: any[] = [];
    try {
      const v = wx.getStorageSync(RECORDS_KEY);
      records = Array.isArray(v) ? v : [];
    } catch (_) {}

    const exists = records.some((it) => this.makeKey(it) === key);
    if (exists) {
      const next = records.filter((it) => this.makeKey(it) !== key);
      try {
        wx.setStorageSync(RECORDS_KEY, next);
      } catch (_) {}
      this.setData({ isRecorded: false });
      wx.showToast({ title: '已移出行程', icon: 'none' });
      return;
    }

    const now = new Date();
    const time = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
      now.getDate()
    ).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const record = Object.assign({}, item, { note: '', recordedAt: time });
    let next = [record].concat(records);
    if (next.length > 300) next = next.slice(0, 300);
    try {
      wx.setStorageSync(RECORDS_KEY, next);
    } catch (_) {}
    this.setData({ isRecorded: true });
    wx.showToast({ title: '已加入行程', icon: 'none' });
  },

  onOpenLink() {
    const url = this.data.officialUrl || this.data.detailUrl;
    if (!url) {
      wx.showToast({ title: '暂无官方链接', icon: 'none' });
      return;
    }
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '官方链接已复制', icon: 'none' })
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
