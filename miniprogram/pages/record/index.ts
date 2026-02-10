// pages/record/index.ts
const KEY = 'my_records';

Page({
  data: {
    items: [] as any[],
    formArtist: '' as string,
    formDetail: '' as string,
    formNote: '' as string,
    formDate: '' as string,
    typeOptions: ['回归', '演唱会', '签售', '活动', '自定义'] as string[],
    typeIndex: 0 as number,
    showCreate: false as boolean
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
    // 最新记录在前
    items = items.slice().sort((a, b) => String(b.recordedAt || '').localeCompare(String(a.recordedAt || '')));
    this.setData({ items });
  },

  onFormInput(e: WechatMiniprogram.Input) {
    const field = e.currentTarget.dataset.field as string;
    const value = e && e.detail && typeof e.detail.value === 'string' ? e.detail.value : '';
    if (!field) return;
    const data: any = {};
    data[field] = value;
    this.setData(data);
  },

  onDateChange(e: WechatMiniprogram.DatePickerChange) {
    const value = e && e.detail && typeof e.detail.value === 'string' ? e.detail.value : '';
    this.setData({ formDate: value });
  },

  onTypeChange(e: WechatMiniprogram.PickerChange) {
    const value = e && e.detail && typeof e.detail.value === 'string' ? parseInt(e.detail.value, 10) : 0;
    this.setData({ typeIndex: isNaN(value) ? 0 : value });
  },

  onCreateRecord() {
    const artist = (this.data.formArtist || '').trim();
    if (!artist) {
      wx.showToast({ title: '请填写标题', icon: 'none' });
      return;
    }
    const detail = (this.data.formDetail || '').trim() || '自定义记录';
    const note = (this.data.formNote || '').trim();
    const dateKey = (this.data.formDate || '').trim();
    const type = (this.data.typeOptions || [])[this.data.typeIndex] || '回归';
    const now = new Date();
    const time = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
      now.getDate()
    ).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    const record = {
      id: now.getTime(),
      artist,
      type,
      date: dateKey ? dateKey.slice(5) : '',
      dateKey,
      detail,
      note,
      recordedAt: time,
      custom: true
    };

    let items: any[] = [];
    try {
      const v = wx.getStorageSync(KEY);
      items = Array.isArray(v) ? v : [];
    } catch (_) {}
    items = [record].concat(items);
    if (items.length > 300) items = items.slice(0, 300);
    try {
      wx.setStorageSync(KEY, items);
    } catch (_) {}

    this.setData({
      formArtist: '',
      formDetail: '',
      formNote: '',
      formDate: '',
      showCreate: false
    });
    wx.showToast({ title: '已添加记录', icon: 'none' });
    this.refresh();
  },

  onOpenCreate() {
    this.setData({ showCreate: true });
  },

  onCloseCreate() {
    this.setData({ showCreate: false });
  },

  onOpen(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const item = (this.data.items || [])[index];
    if (!item) return;
    const app = getApp<IAppOption>();
    app.globalData.eventDetail = item;
    wx.navigateTo({ url: '/pages/event-detail/index' });
  },

  onEdit(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const item = (this.data.items || [])[index];
    if (!item) return;
    const current = item.note || '';
    wx.showModal({
      title: '编辑记录',
      editable: true,
      placeholderText: '写下追回归的repo…',
      content: current,
      success: (res) => {
        if (!res.confirm) return;
        const note = (res.content || '').trim();
        const now = new Date();
        const time = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
          now.getDate()
        ).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        item.note = note;
        item.recordedAt = time;
        const items = (this.data.items || []).slice();
        items[index] = item;
        try {
          wx.setStorageSync(KEY, items);
        } catch (_) {}
        this.refresh();
      }
    });
  },

  onRemove(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const items = (this.data.items || []).slice();
    items.splice(index, 1);
    try {
      wx.setStorageSync(KEY, items);
    } catch (_) {}
    this.refresh();
  }
});

