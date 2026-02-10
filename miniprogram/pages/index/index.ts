// pages/index/index.ts
import { SCHEDULE_API_BASE } from '../../utils/config';

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
const FILTER_TABS = [
  { key: '全部', label: '全部' },
  { key: '回归', label: '回归' },
  { key: '演唱会', label: '演唱会' },
  { key: '签售', label: '签售' },
  { key: '活动', label: '活动' }
];

const FAVORITES_KEY = 'my_favorites';
const RECORDS_KEY = 'my_records';

interface ScheduleItem {
  id: number;
  artist: string;
  type: string;   // 回归 | 演唱会 | 签售 | 活动
  date: string;
  dateKey: string;
  detail: string;
  ticketPlatform?: string;  // 购票平台：NOL / Melon / YES24 等
  ticketTime?: string;      // 场馆
  showTime?: string;        // 开场时间
  detailUrl?: string;       // 详情/购票链接
  locationText?: string;    // 活动地点/区域（活动 tab 用）
  coverImage?: string;      // 活动/票务封面（可选）
  _isFavorite?: boolean;    // 本地收藏标记（仅前端）
  _isRecorded?: boolean;    // 本地记录标记（仅前端）
}

Page({
  data: (() => {
    const now = new Date();
    return {
      schedules: [] as ScheduleItem[],
      searchText: '' as string,
      searchOpen: false as boolean,
      searchResults: [] as ScheduleItem[],
      filterTabs: FILTER_TABS,
      filterType: '全部' as string,
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      monthLabel: '',
      calendarDays: [] as { day: number; dateKey: string; isCurrentMonth: boolean; isToday: boolean; hasEvent: boolean }[],
      selectedDateKey: '',
      selectedDaySchedules: [] as ScheduleItem[],
      weekdays: WEEKDAYS
    };
  })(),

  onLoad() {
    this.loadLocalData();
    this.setMonthLabel();
  },

  onShow() {
    // 从记录页返回时，刷新卡片上的记录/收藏状态
    this.updateSelectedDaySchedules();
  },

  onSearchFocus() {
    // 有内容时才打开弹层；避免空输入时挡住页面
    const q = (this.data.searchText || '').trim();
    if (q) {
      this.applySearch(q);
    } else {
      this.setData({ searchOpen: false, searchResults: [] });
    }
  },

  onSearchBlur() {
    // 让点击结果项的 tap 先触发，再关闭弹层
    if ((this as any)._searchBlurTimer) clearTimeout((this as any)._searchBlurTimer);
    (this as any)._searchBlurTimer = setTimeout(() => {
      this.setData({ searchOpen: false });
    }, 250);
  },

  onSearchClear() {
    if ((this as any)._searchTimer) clearTimeout((this as any)._searchTimer);
    this.setData({ searchText: '', searchOpen: false, searchResults: [] });
  },

  onSearchInput(e: WechatMiniprogram.Input) {
    const value = e && e.detail && typeof e.detail.value === 'string' ? e.detail.value : '';
    this.setData({ searchText: value });

    if ((this as any)._searchTimer) clearTimeout((this as any)._searchTimer);
    (this as any)._searchTimer = setTimeout(() => {
      const q = (value || '').trim();
      this.applySearch(q);
    }, 150);
  },

  applySearch(query: string) {
    const q = (query || '').trim();
    if (!q) {
      this.setData({ searchOpen: false, searchResults: [] });
      return;
    }

    const qn = q.toLowerCase();
    const schedules = this.data.schedules as ScheduleItem[];
    const results: Array<
      ScheduleItem & {
        _matchField?: 'artist' | 'detail';
        _matchIndex?: number;
        _displayDetail?: string;
        _score?: string;
      }
    > = [];
    const seen = new Set<string>();

    const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const isAsciiQuery = /^[a-z0-9\s._-]+$/i.test(q);
    const normalizeAscii = (s: string) => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
    const wordBoundaryIndex = (textLower: string, needleLower: string) => {
      if (!needleLower) return -1;
      // 仅对 ASCII 的“整词”做边界匹配；中文/韩文等用 substring 即可
      if (!isAsciiQuery) return textLower.indexOf(needleLower);
      const re = new RegExp(`(^|[^a-z0-9])(${escapeRegExp(needleLower)})([^a-z0-9]|$)`, 'i');
      const m = re.exec(textLower);
      if (!m) return -1;
      // m.index 指向整段匹配的开头（可能包含前置边界字符），把它修正到关键词本身的起始位置
      const lead = m[1] ? m[1].length : 0;
      return m.index + lead;
    };

    const makeSnippet = (text: string, idx: number) => {
      const raw = text || '';
      if (idx <= 0) return raw;
      const start = idx;
      const end = Math.min(raw.length, start + 48);
      const slice = raw.slice(start, end).trim();
      return slice ? (slice + (end < raw.length ? '…' : '')) : raw;
    };

    for (let i = 0; i < schedules.length; i++) {
      const s = schedules[i];
      // 需求：搜索引擎不包含「活动」
      if (s && s.type === '活动') continue;
      const artistRaw = s.artist || '';
      const detailRaw = s.detail || '';
      const artist = artistRaw.toLowerCase();
      const detail = detailRaw.toLowerCase();
      const artistIdx = wordBoundaryIndex(artist, qn);
      const detailIdx = wordBoundaryIndex(detail, qn);

      // “整体关键词”策略：优先 artist 命中；其次 detail 命中
      let field: 'artist' | 'detail' | '' = '';
      let idx = -1;
      if (artistIdx >= 0) {
        field = 'artist';
        idx = artistIdx;
      } else if (detailIdx >= 0) {
        field = 'detail';
        idx = detailIdx;
      }
      if (!field) continue;

      const key = `${s.detailUrl || ''}|${s.dateKey || ''}|${s.type || ''}|${s.artist || ''}|${s.detail || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const fieldTextRaw = field === 'artist' ? artistRaw : detailRaw;
      const fieldTextLower = field === 'artist' ? artist : detail;
      const exactHit =
        (fieldTextLower.trim() === qn) ||
        (isAsciiQuery && normalizeAscii(fieldTextRaw) === normalizeAscii(q));
      const prefixHit = fieldTextLower.trim().indexOf(qn) === 0;
      const fieldPri = field === 'artist' ? 0 : 1;
      const idxNorm = idx < 0 ? 9999 : idx;
      // 排序优先级（越靠前越优先）：
      // 1) 完全相等（IVE） 2) 整词匹配（" IVE "） 3) 开头匹配（IVE...） 4) 字段优先（artist > detail） 5) 越靠前越优先
      const exactPri = exactHit ? 0 : 1;
      const wordPri = idx >= 0 ? 0 : 1;
      const prefixPri = prefixHit ? 0 : 1;
      const score = `${exactPri}|${wordPri}|${prefixPri}|${String(fieldPri)}|${String(idxNorm).padStart(4, '0')}`;

      // 注意：不要使用对象展开（...），否则会引入 @babel/runtime 的 objectSpread2 依赖
      results.push({
        id: (s as any).id,
        artist: s.artist,
        type: s.type,
        date: s.date,
        dateKey: s.dateKey,
        detail: s.detail,
        ticketPlatform: s.ticketPlatform,
        ticketTime: s.ticketTime,
        showTime: s.showTime,
        detailUrl: s.detailUrl,
        locationText: (s as any).locationText,
        coverImage: (s as any).coverImage,
        _matchField: field,
        _matchIndex: idx,
        _displayDetail: field === 'detail' ? makeSnippet(detailRaw, idx) : detailRaw,
        _score: score
      } as any);
    }

    results.sort((a, b) => {
      const sa = a._score || '';
      const sb = b._score || '';
      if (sa !== sb) return sa < sb ? -1 : 1;
      const da = a.dateKey || '';
      const db = b.dateKey || '';
      if (da !== db) return db.localeCompare(da); // 日期新 → 旧
      return (a.artist || '').localeCompare(b.artist || '');
    });

    this.setData({
      searchOpen: true,
      searchResults: (results.slice(0, 20) as any)
    });
  },

  onSearchResultTap(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const list = this.data.searchResults as ScheduleItem[];
    const item = list[index];
    if (!item) return;

    if ((this as any)._searchBlurTimer) clearTimeout((this as any)._searchBlurTimer);
    this.setData({ searchOpen: false });

    // 同步日历状态：跳到对应日期与类型（否则“全部”不会展示活动）
    const dateKey = item.dateKey || '';
    const filterType = item.type || '全部';
    this.setData({
      selectedDateKey: dateKey || this.data.selectedDateKey,
      filterType
    });
    this.buildCalendar();

    // 打开详情
    const app = getApp<IAppOption>();
    app.globalData.eventDetail = {
      id: item.id,
      artist: item.artist,
      type: item.type,
      date: item.date,
      dateKey: item.dateKey,
      detail: item.detail,
      ticketPlatform: item.ticketPlatform,
      ticketTime: item.ticketTime,
      showTime: item.showTime,
      detailUrl: item.detailUrl,
      locationText: item.locationText,
      coverImage: item.coverImage
    };
    wx.navigateTo({ url: '/pages/event-detail/index' });
  },

  setMonthLabel() {
    const { year, month } = this.data;
    this.setData({
      monthLabel: `${year}年${month}月`
    });
    this.buildCalendar();
  },

  // 构建日历网格：上月尾、本月、下月头。按当前筛选类型决定哪些日期显示圆点
  buildCalendar() {
    const { year, month, schedules, filterType } = this.data;
    const first = new Date(year, month - 1, 1);
    const last = new Date(year, month, 0);
    const firstWeekday = first.getDay();
    const daysInMonth = last.getDate();
    const today = new Date();
    const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    const list = (() => {
      // 需求：全部 tab 不展示「活动」卡片（活动只在「活动」tab 里看）
      if (filterType === '全部') return (schedules as ScheduleItem[]).filter(s => s.type !== '活动');
      if (filterType === '签售') return (schedules as ScheduleItem[]).filter(s => s.type === '签售' && s.ticketPlatform === 'Ktown4u');
      return (schedules as ScheduleItem[]).filter(s => s.type === filterType);
    })();
    const eventKeys = new Set(list.map((s: ScheduleItem) => s.dateKey));

    const days: { day: number; dateKey: string; isCurrentMonth: boolean; isToday: boolean; hasEvent: boolean }[] = [];

    // 上月末尾几天
    const prevMonth = month === 1 ? 12 : month - 1;
    const prevYear = month === 1 ? year - 1 : year;
    const prevLast = new Date(prevYear, prevMonth, 0);
    const prevDaysCount = prevLast.getDate();
    for (let i = firstWeekday - 1; i >= 0; i--) {
      const d = prevDaysCount - i;
      const dateKey = `${prevYear}-${String(prevMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      days.push({
        day: d,
        dateKey,
        isCurrentMonth: false,
        isToday: dateKey === todayKey,
        hasEvent: eventKeys.has(dateKey)
      });
    }

    // 本月
    for (let d = 1; d <= daysInMonth; d++) {
      const dateKey = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      days.push({
        day: d,
        dateKey,
        isCurrentMonth: true,
        isToday: dateKey === todayKey,
        hasEvent: eventKeys.has(dateKey)
      });
    }

    // 下月开头，凑满 6 行
    const total = days.length;
    const rest = total % 7 === 0 ? 0 : 7 - (total % 7);
    const nextMonth = month === 12 ? 1 : month + 1;
    const nextYear = month === 12 ? year + 1 : year;
    for (let d = 1; d <= rest; d++) {
      const dateKey = `${nextYear}-${String(nextMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      days.push({
        day: d,
        dateKey,
        isCurrentMonth: false,
        isToday: dateKey === todayKey,
        hasEvent: eventKeys.has(dateKey)
      });
    }

    this.setData({
      calendarDays: days,
      selectedDateKey: this.data.selectedDateKey || todayKey
    });
    this.updateSelectedDaySchedules();
  },

  updateSelectedDaySchedules() {
    const { schedules, selectedDateKey, filterType } = this.data;
    let list = (schedules as ScheduleItem[]).filter(s => s.dateKey === selectedDateKey);
    if (filterType === '全部') {
      // 需求：全部 tab 不展示「活动」卡片
      list = list.filter(s => s.type !== '活动');
    } else if (filterType === '签售') {
      list = list.filter(s => s.type === '签售' && s.ticketPlatform === 'Ktown4u');
    } else {
      list = list.filter(s => s.type === filterType);
    }
    const favSet = this.getFavoriteSet();
    const recSet = this.getRecordSet();
    const next: ScheduleItem[] = [];
    for (let i = 0; i < list.length; i++) {
      const s = list[i];
      const key = this.makeKey(s);
      next.push({
        id: s.id,
        artist: s.artist,
        type: s.type,
        date: s.date,
        dateKey: s.dateKey,
        detail: s.detail,
        ticketPlatform: s.ticketPlatform,
        ticketTime: s.ticketTime,
        showTime: s.showTime,
        detailUrl: s.detailUrl,
        locationText: s.locationText,
        coverImage: s.coverImage,
        _isFavorite: favSet.has(key),
        _isRecorded: recSet.has(key)
      });
    }
    this.setData({ selectedDaySchedules: next });
  },

  onFilterTap(e: WechatMiniprogram.TouchEvent) {
    const filterType = e.currentTarget.dataset.filter as string;
    this.setData({ filterType });
    this.buildCalendar();
  },

  prevMonth() {
    let { year, month } = this.data;
    if (month === 1) {
      month = 12;
      year -= 1;
    } else {
      month -= 1;
    }
    this.setData({ year, month });
    this.setMonthLabel();
  },

  nextMonth() {
    let { year, month } = this.data;
    if (month === 12) {
      month = 1;
      year += 1;
    } else {
      month += 1;
    }
    this.setData({ year, month });
    this.setMonthLabel();
  },

  onDayTap(e: WechatMiniprogram.TouchEvent) {
    const dateKey = e.currentTarget.dataset.dateKey as string;
    this.setData({ selectedDateKey: dateKey });
    this.updateSelectedDaySchedules();
  },

  onScheduleItemTap(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const list = this.data.selectedDaySchedules as ScheduleItem[];
    const item = list[index];
    if (!item) return;
    const app = getApp<IAppOption>();
    app.globalData.eventDetail = {
      id: item.id,
      artist: item.artist,
      type: item.type,
      date: item.date,
      dateKey: item.dateKey,
      detail: item.detail,
      ticketPlatform: item.ticketPlatform,
      ticketTime: item.ticketTime,
      showTime: item.showTime,
      detailUrl: item.detailUrl,
      locationText: item.locationText,
      coverImage: item.coverImage
    };
    wx.navigateTo({ url: '/pages/event-detail/index' });
  },

  makeKey(item: ScheduleItem) {
    return `${item.detailUrl || ''}|${item.dateKey || ''}|${item.type || ''}|${item.artist || ''}|${item.detail || ''}`;
  },

  getFavoriteSet(): Set<string> {
    try {
      const v = wx.getStorageSync(FAVORITES_KEY);
      const arr = Array.isArray(v) ? v : [];
      const set = new Set<string>();
      for (let i = 0; i < arr.length; i++) {
        const it = arr[i] as ScheduleItem;
        set.add(this.makeKey(it));
      }
      return set;
    } catch (_) {
      return new Set<string>();
    }
  },

  getRecordSet(): Set<string> {
    try {
      const v = wx.getStorageSync(RECORDS_KEY);
      const arr = Array.isArray(v) ? v : [];
      const set = new Set<string>();
      for (let i = 0; i < arr.length; i++) {
        const it = arr[i] as any;
        set.add(this.makeKey(it));
      }
      return set;
    } catch (_) {
      return new Set<string>();
    }
  },

  onToggleFavorite(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const list = this.data.selectedDaySchedules as ScheduleItem[];
    const item = list[index];
    if (!item) return;

    const key = this.makeKey(item);
    let arr: ScheduleItem[] = [];
    try {
      const v = wx.getStorageSync(FAVORITES_KEY);
      arr = Array.isArray(v) ? v : [];
    } catch (_) {}

    const exists = arr.some((it) => this.makeKey(it) === key);
    if (exists) {
      arr = arr.filter((it) => this.makeKey(it) !== key);
      wx.showToast({ title: '已取消收藏', icon: 'none' });
    } else {
      arr = [item].concat(arr);
      if (arr.length > 200) arr = arr.slice(0, 200);
      wx.showToast({ title: '已加入收藏', icon: 'none' });
    }
    try {
      wx.setStorageSync(FAVORITES_KEY, arr);
    } catch (_) {}
    this.updateSelectedDaySchedules();
  },

  onRecordTap(e: WechatMiniprogram.TouchEvent) {
    const index = e.currentTarget.dataset.index as number;
    const list = this.data.selectedDaySchedules as ScheduleItem[];
    const item = list[index];
    if (!item) return;

    const key = this.makeKey(item);
    let records: any[] = [];
    try {
      const v = wx.getStorageSync(RECORDS_KEY);
      records = Array.isArray(v) ? v : [];
    } catch (_) {}

    let currentNote = '';
    for (let i = 0; i < records.length; i++) {
      const it = records[i];
      if (this.makeKey(it) === key) {
        currentNote = it.note || '';
        break;
      }
    }

    wx.showModal({
      title: '记录当时心情',
      editable: true,
      placeholderText: '写下追回归的repo…',
      content: currentNote,
      success: (res) => {
        if (!res.confirm) return;
        const note = (res.content || '').trim();
        const now = new Date();
        const time = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
          now.getDate()
        ).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

        const record = {
          id: item.id,
          artist: item.artist,
          type: item.type,
          date: item.date,
          dateKey: item.dateKey,
          detail: item.detail,
          ticketPlatform: item.ticketPlatform,
          ticketTime: item.ticketTime,
          showTime: item.showTime,
          detailUrl: item.detailUrl,
          locationText: item.locationText,
          coverImage: item.coverImage,
          note,
          recordedAt: time
        };

        let next: any[] = [];
        let updated = false;
        for (let i = 0; i < records.length; i++) {
          const it = records[i];
          if (this.makeKey(it) === key) {
            next.push(record);
            updated = true;
          } else {
            next.push(it);
          }
        }
        if (!updated) next.unshift(record);
        if (next.length > 300) next = next.slice(0, 300);
        try {
          wx.setStorageSync(RECORDS_KEY, next);
        } catch (_) {}
        wx.showToast({ title: '已记录', icon: 'none' });
        this.updateSelectedDaySchedules();
      }
    });
  },


  normalizeDate(dateStr: string): string {
    if (!dateStr) return '';
    const y = new Date().getFullYear();
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
    if (/^\d{2}-\d{2}$/.test(dateStr)) return `${y}-${dateStr}`;
    return '';
  },

  /** 优先从后端 API 拉取（每 12 小时爬一次），失败则用本地 data/*.js */
  loadLocalData() {
    if (SCHEDULE_API_BASE) {
      wx.request({
        url: SCHEDULE_API_BASE.replace(/\/$/, '') + '/api/schedules',
        method: 'GET',
        success: (res: WechatMiniprogram.RequestSuccessCallbackResult) => {
          const data = res.data as { schedules?: ScheduleItem[] };
          const schedules = data && Array.isArray((data as any).schedules) ? (data as any).schedules as ScheduleItem[] : [];
          if (res.statusCode === 200 && schedules.length > 0) {
            const list = schedules.map((item, i) => ({
              id: typeof (item as any).id === 'number' ? (item as any).id : i + 1,
              artist: item.artist || '未知',
              type: item.type || '回归',
              date: item.date || (item.dateKey ? item.dateKey.slice(5) : '') || '',
              dateKey: item.dateKey || '',
              detail: item.detail || '回归',
              ticketPlatform: item.ticketPlatform,
              ticketTime: item.ticketTime,
              showTime: item.showTime,
              detailUrl: item.detailUrl,
              locationText: (item as any).locationText,
              coverImage: (item as any).coverImage
            }));
            this.setData({ schedules: list });
            this.buildCalendar();
            return;
          }
          this.loadLocalDataFallback();
        },
        fail: () => {
          this.loadLocalDataFallback();
        }
      });
    } else {
      this.loadLocalDataFallback();
    }
  },

  loadLocalDataFallback() {
    const list: ScheduleItem[] = [];
    let id = 0;
    const push = (
      item: ScheduleItem & {
        ticketPlatform?: string;
        ticketTime?: string;
        showTime?: string;
        detailUrl?: string;
        locationText?: string;
        coverImage?: string;
      }
    ) => {
      id += 1;
      list.push({
        id,
        artist: item.artist || '未知',
        type: item.type || '回归',
        date: item.date || (item.dateKey ? item.dateKey.slice(5) : '') || '',
        dateKey: item.dateKey || '',
        detail: item.detail || '回归',
        ticketPlatform: item.ticketPlatform,
        ticketTime: item.ticketTime,
        showTime: item.showTime,
        detailUrl: item.detailUrl,
        locationText: item.locationText,
        coverImage: item.coverImage
      });
    };
    try {
      const comebacks = require('../../data/comebacks.js') as ScheduleItem[];
      console.log('[加载回归数据] 成功加载，条数:', Array.isArray(comebacks) ? comebacks.length : 0);
      if (Array.isArray(comebacks) && comebacks.length > 0) {
        comebacks.forEach(item => push(item));
        console.log('[加载回归数据] 已添加', comebacks.length, '条回归数据');
      }
    } catch (e) {
      console.error('[加载回归数据] 失败:', e);
    }
    try {
      const concerts = require('../../data/concerts.js') as ScheduleItem[];
      if (Array.isArray(concerts) && concerts.length > 0) concerts.forEach(item => push(item));
    } catch (_) {}
    try {
      const ticketConcerts = require('../../data/ticket_concerts.js') as ScheduleItem[];
      if (Array.isArray(ticketConcerts) && ticketConcerts.length > 0) ticketConcerts.forEach(item => push(item));
    } catch (_) {}
    try {
      const melonConcerts = require('../../data/melon_concerts.js') as ScheduleItem[];
      if (Array.isArray(melonConcerts) && melonConcerts.length > 0) melonConcerts.forEach(item => push(item));
    } catch (_) {}
    try {
      const fansigns = require('../../data/fansigns.js') as ScheduleItem[];
      if (Array.isArray(fansigns) && fansigns.length > 0) fansigns.forEach(item => push(item));
    } catch (_) {}
    try {
      const festas = require('../../data/festas.js') as ScheduleItem[];
      if (Array.isArray(festas) && festas.length > 0) festas.forEach(item => push(item));
    } catch (_) {}
    if (list.length === 0) {
      const y = 2026;
      push({ artist: 'IVE', type: '回归', date: '02-15', dateKey: `${y}-02-15`, detail: '新专辑回归' });
      push({ artist: 'G-DRAGON', type: '演唱会', date: '02-06', dateKey: `${y}-02-06`, detail: 'FAM MEETING 2026 · Seoul' });
      push({ artist: 'LNGSHOT', type: '签售', date: '02-09', dateKey: `${y}-02-09`, detail: 'Fansign Event · London' });
      push({ artist: 'BTS THE COMEBACK LIVE 购票指南', type: '活动', date: '02-09', dateKey: `${y}-02-09`, detail: '娱乐 · 光化门', locationText: '娱乐 · 光化门', detailUrl: 'https://world.nol.com/zh-CN/regions/b263b346-9a60-49d5-949a-dc88dfbea53e/festas' });
    }
    list.sort((a, b) => a.dateKey.localeCompare(b.dateKey) || a.type.localeCompare(b.type));
    console.log('[数据加载完成] 总条数:', list.length);
    console.log('[数据加载完成] 回归条数:', list.filter(s => s.type === '回归').length);
    console.log('[数据加载完成] 日期范围:', list.length > 0 ? `${list[0].dateKey} 到 ${list[list.length - 1].dateKey}` : '无数据');
    this.setData({ schedules: list });
    this.buildCalendar();
  }
});
