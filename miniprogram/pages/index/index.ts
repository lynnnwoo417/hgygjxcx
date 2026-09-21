// pages/index/index.ts
import { getCalendarEvents, getEvents, hasRemoteApi, searchEvents } from '../../utils/api';

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

function localizeReleaseDetail(detail: string): string {
  const raw = detail || '回归';
  return raw
    .replace(/^pre-release\s+/i, '先行 ')
    .replace(/^Japanese\s+/i, '日语 ')
    .replace(/^Korean\s+/i, '韩语 ')
    .replace(/^full-length album/i, '正规专辑')
    .replace(/^full album/i, '正规专辑')
    .replace(/^mini album/i, '迷你专辑')
    .replace(/^digital single/i, '数字单曲')
    .replace(/^single album/i, '单曲专辑')
    .replace(/^special single/i, '特别单曲')
    .replace(/^single/i, '单曲')
    .replace(/^EP\b/i, 'EP');
}

function looksLikeClockOrSaleTime(text: string): boolean {
  const s = (text || '').trim();
  if (!s) return false;
  return (
    /^\d{1,2}:\d{2}/.test(s) ||
    /\d{1,2}:\d{2}\s*(kst|jst|cst|sgt)/i.test(s) ||
    /(开票|预售|onsale|on sale|ticket time)/i.test(s)
  );
}

/** 票务爬虫曾把场馆误写入 ticketTime；加载时纠正，不伪造新地点。 */
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

/** 国家/地区：点当前国旗下滑展开，再点目标旗帜 */
const REGION_TABS = [
  { key: 'KR', flag: '🇰🇷', label: '韩国' },
  { key: 'JP', flag: '🇯🇵', label: '日本' },
  { key: 'CN', flag: '🇨🇳', label: '中国大陆' },
  { key: 'HK', flag: '🇭🇰', label: '中国香港' },
  { key: 'MO', flag: '🇲🇴', label: '中国澳门' },
  { key: 'US', flag: '🇺🇸', label: '美国' },
  { key: 'OTHER', flag: '🌍', label: '其他地区' }
];

function regionFlagOf(key: string): string {
  for (let i = 0; i < REGION_TABS.length; i++) {
    if (REGION_TABS[i].key === key) return REGION_TABS[i].flag;
  }
  return '🇰🇷';
}

function regionLabelOf(key: string): string {
  for (let i = 0; i < REGION_TABS.length; i++) {
    if (REGION_TABS[i].key === key) return REGION_TABS[i].label;
  }
  return '韩国';
}

function chinaAreaLabel(region: string): string {
  if (region === 'HK') return '中国香港';
  if (region === 'MO') return '中国澳门';
  if (region === 'TW') return '中国台湾';
  return '';
}

/**
 * 地区识别词表。顺序即优先级：
 * 港澳台要排在「中国大陆」前面（'Hong Kong, China' 不能被 'china' 抢先命中）。
 */
const REGION_RULES: Array<{ region: string; hints: string[] }> = [
  {
    region: 'HK',
    hints: ['hong kong', 'hongkong', '香港', 'kai tak', 'asiaworld', 'asia world-expo']
  },
  {
    region: 'MO',
    hints: ['macau', 'macao', '澳门', '澳門']
  },
  {
    region: 'TW',
    hints: ['taiwan', 'taipei', 'kaohsiung', 'taichung', 'tainan', '台湾', '台灣', '台北', '高雄', '台中']
  },
  {
    region: 'KR',
    hints: [
      'korea', '한국', '서울', 'seoul', '首尔',
      // 韩国其他市道（韩文 / 罗马字 / 中文）
      '경기', '인천', '부산', '대구', '대전', '광주', '울산', '제주', '전북', '전남', '강원', '충북', '충남', '경북', '경남', '세종',
      'goyang', 'incheon', 'busan', 'daegu', 'daejeon', 'gwangju', 'ulsan', 'jeju', 'suwon', 'yongin',
      'cheongju', 'gapyeong', 'paju', 'ansan', 'anyang', 'bucheon', 'seongnam', 'gyeonggi', 'jeonju',
      'changwon', 'gimhae', 'wonju', 'gangneung', 'pyeongtaek', 'sasang-gu',
      // 韩国常见场馆
      'kspo', 'gocheok', 'kintex', 'inspire arena', 'bexco', 'exco', 'yes24', 'jangchung',
      'blue square', 'bluesquare', 'sangsangmadang', 'jarasum', 'paradise city', 'olympic hall',
      'olympic park', 'olympicpark', 'sejong center', 'kbs arena', 'kbs부산홀',
      // festas 的中文区域名
      '光化门', '弘大', '圣水', '江南', '东大门', '梨泰院', '汝矣岛', '蚕室', '龙山', '明洞', '钟路', '合井', '建大', '新村',
      '水原', '仁川', '釜山', '大邱', '济州', '高阳'
    ]
  },
  {
    region: 'JP',
    hints: [
      'japan', 'tokyo', 'osaka', 'saitama', 'chiba', 'nagoya', 'fukuoka', 'kobe', 'kyoto',
      'yokohama', 'sapporo', 'hiroshima', 'makuhari', 'okinawa', 'nagasaki', 'kanagawa',
      '日本', '东京', '大阪', '名古屋', '福冈'
    ]
  },
  {
    region: 'CN',
    hints: [
      'china', '中国', 'shanghai', 'beijing', 'guangzhou', 'shenzhen', 'chengdu', 'chongqing',
      'hangzhou', 'nanjing', 'wuhan', 'xi\'an', 'qingdao', 'shenyang',
      '上海', '北京', '广州', '深圳', '成都', '重庆', '杭州', '南京', '武汉'
    ]
  },
  {
    region: 'US',
    hints: [
      'united states', ', us', 'nevada', 'new york', 'los angeles', 'california',
      'texas', 'chicago', 'washington', 'las vegas', 'brooklyn', 'america'
    ]
  },
  {
    region: 'OTHER',
    hints: [
      'canada', 'mexico', 'colombia', 'bogota', 'argentina', 'buenos aires',
      'brazil', 'sao paulo', 'chile', 'santiago', 'peru', 'lima',
      'ontario', 'vancouver', 'toronto',
      // 亚太（韩日中以外）
      'singapore', 'thailand', 'bangkok', 'malaysia', 'kuala lumpur', 'indonesia', 'jakarta',
      'philippines', 'manila', 'bulacan', 'cebu', 'vietnam', 'hanoi', 'ho chi minh', 'cambodia',
      'australia', 'sydney', 'melbourne', 'brisbane', 'new zealand', 'auckland', 'india', 'mumbai',
      // 欧洲 / 中东
      'united kingdom', 'london', 'manchester', 'ireland', 'dublin', 'france', 'paris', 'germany',
      'berlin', 'hamburg', 'netherlands', 'amsterdam', 'belgium', 'brussels', 'spain', 'madrid',
      'barcelona', 'italy', 'milan', 'rome', 'poland', 'warsaw', 'sweden', 'stockholm', 'denmark',
      'copenhagen', 'switzerland', 'zurich', 'austria', 'vienna', 'portugal', 'lisbon', 'czech',
      'prague', 'hungary', 'budapest', 'turkey', 'istanbul', 'dubai', 'abu dhabi', 'saudi', 'qatar'
    ]
  }
];

function hasHint(text: string, hints: string[]): boolean {
  return hints.some(hint => text.indexOf(hint) >= 0);
}

function matchRegion(text: string): string {
  const t = (text || '').toLowerCase();
  if (!t.trim()) return '';
  for (let i = 0; i < REGION_RULES.length; i++) {
    if (hasHint(t, REGION_RULES[i].hints)) return REGION_RULES[i].region;
  }
  return '';
}

/**
 * 推断一条日程属于哪个国家/地区：地点字段 > 场馆 > 标题详情。
 * 回归没有地点（且标题里常出现「日语专辑」这类词），统一归到韩国，避免被误判。
 * 完全认不出来的按韩国算——数据源本身以韩国为主，不凭空丢掉真实数据。
 */
function detectRegion(item: { type?: string; venue?: string; locationText?: string; detail?: string }): string {
  if ((item.type || '') === '回归') return 'KR';
  const loc = (item.locationText || '').trim();
  if (loc) {
    const byLoc = matchRegion(loc);
    if (byLoc) return byLoc;
    // 「城市, 国家」这类英文地点，没提到韩国就按海外算
    if (/[a-z]/i.test(loc)) return 'OTHER';
  }
  const byVenue = matchRegion(item.venue || '');
  if (byVenue) return byVenue;
  const byDetail = matchRegion(item.detail || '');
  if (byDetail) return byDetail;
  return 'KR';
}

function decoratePlace(item: {
  type?: string;
  ticketTime?: string;
  venue?: string;
  locationText?: string;
  detail?: string;
}): { ticketTime?: string; venue?: string; locationText?: string; displayLocation?: string; region: string } {
  const split = splitTicketAndVenue(item);
  const region = detectRegion({
    type: item.type,
    venue: split.venue,
    locationText: split.locationText,
    detail: item.detail
  });
  const area = chinaAreaLabel(region);
  return {
    ...split,
    displayLocation: area || undefined,
    region
  };
}

function hydrateSchedule(item: any, index: number): ScheduleItem {
  const place = decoratePlace(item);
  return {
    id: typeof item.id === 'number' ? item.id : index + 1,
    artist: item.artist || '未知',
    type: item.type || '回归',
    date: item.date || (item.dateKey ? String(item.dateKey).slice(5) : '') || '',
    dateKey: item.dateKey || '',
    detail: localizeReleaseDetail(item.detail || '回归'),
    ticketPlatform: item.ticketPlatform,
    ticketTime: place.ticketTime,
    venue: place.venue,
    locationText: place.locationText,
    displayLocation: place.displayLocation,
    showTime: item.showTime,
    detailUrl: item.detailUrl,
    officialUrl: item.officialUrl,
    coverImage: item.coverImage,
    region: place.region || item.region
  };
}

function toDateLabel(now: Date): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

interface ScheduleItem {
  id: number;
  artist: string;
  type: string;   // 回归 | 演唱会 | 签售 | 活动
  date: string;
  dateKey: string;
  detail: string;
  ticketPlatform?: string;  // 购票/报名平台
  ticketTime?: string;      // 开票时间（若有）
  venue?: string;           // 场馆
  showTime?: string;        // 活动/发布时间
  detailUrl?: string;       // 详情/购票链接
  officialUrl?: string;     // 官方购票/报名链接（若有）
  locationText?: string;    // 地点/区域
  displayLocation?: string; // 展示用：中国香港 / 中国澳门 / 中国台湾
  coverImage?: string;      // 活动/票务封面（可选）
  region?: string;          // 加载时推断：KR|JP|CN|US|HK|MO|TW|OTHER
  _isFavorite?: boolean;    // 本地收藏标记（仅前端）
  _isRecorded?: boolean;    // 本地行程标记（仅前端）
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
      regionTabs: REGION_TABS,
      regionKey: 'KR' as string,
      regionFlag: '🇰🇷' as string,
      regionOpen: false as boolean,
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      monthLabel: '',
      calendarHint: '看看你在韩国的这几天，有哪些活动可以参加',
      calendarDays: [] as { day: number; dateKey: string; isCurrentMonth: boolean; isToday: boolean; hasEvent: boolean }[],
      selectedDateKey: '',
      selectedDaySchedules: [] as ScheduleItem[],
      upcomingCount: 0,
      upcomingCountText: '接下来有 0 场活动',
      dayPanelOpen: false,
      dataUpdatedAt: toDateLabel(now),
      weekdays: WEEKDAYS
    };
  })(),

  onLoad() {
    this.loadLocalData();
    this.setMonthLabel();
  },

  onShow() {
    // 从行程页返回时，刷新卡片上的行程/收藏状态
    this.updateSelectedDaySchedules();
    this.buildUpcomingOverview();
  },

  /** 概览文案里用的地区名，「其他地区」口语化成「海外」 */
  currentRegionLabel(): string {
    return regionLabelOf(this.data.regionKey);
  },

  currentCalendarHint(): string {
    const label = this.currentRegionLabel() || '韩国';
    return `看看你在${label}的这几天，有哪些活动可以参加`;
  },

  inSelectedRegion(item: ScheduleItem): boolean {
    const region = item.region || 'KR';
    if (this.data.regionKey === 'OTHER') return region === 'OTHER' || region === 'TW';
    return region === this.data.regionKey;
  },

  onFlagPanelToggle() {
    this.setData({ regionOpen: !this.data.regionOpen });
  },

  onRegionTap(e: WechatMiniprogram.TouchEvent) {
    const regionKey = e.currentTarget.dataset.region as string;
    if (!regionKey) return;
    this.setData({
      regionKey,
      regionFlag: regionFlagOf(regionKey),
      regionOpen: false
    });
    this.refreshByFilters();
  },

  /** 筛选条件变化后刷新日历圆点、当日日程、计数与搜索结果 */
  refreshByFilters() {
    this.buildCalendar();
    this.buildUpcomingOverview();
    const q = (this.data.searchText || '').trim();
    if (q && this.data.searchOpen) this.applySearch(q);
  },

  buildUpcomingOverview() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const filterType = this.data.filterType;
    let source = (this.data.schedules as ScheduleItem[]).filter(
      item => item.dateKey >= todayKey && this.inSelectedRegion(item)
    );
    if (filterType === '全部') {
      source = source.filter(s => s.type !== '活动');
    } else if (filterType === '签售') {
      source = source.filter(s => s.type === '签售' && s.ticketPlatform === 'Ktown4u');
    } else {
      source = source.filter(s => s.type === filterType);
    }
    const noun = filterType === '全部' ? '活动' : filterType;
    this.setData({
      upcomingCount: source.length,
      upcomingCountText: `接下来有 ${source.length} 场${this.currentRegionLabel()}${noun}`,
      calendarHint: this.currentCalendarHint()
    });
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
    if (hasRemoteApi()) {
      searchEvents(q)
        .then((rows) => {
          const mapped = (rows || []).map((item, i) => hydrateSchedule(item, i));
          const filtered = mapped.filter((s) => this.inSelectedRegion(s));
          this.setData({
            searchOpen: true,
            searchResults: filtered.slice(0, 80)
          });
        })
        .catch(() => {
          this.applySearchLocal(q);
        });
      return;
    }
    this.applySearchLocal(q);
  },

  applySearchLocal(query: string) {
    const q = (query || '').trim();
    if (!q) {
      this.setData({ searchOpen: false, searchResults: [] });
      return;
    }

    const qn = q.toLowerCase();
    const schedules = this.data.schedules as ScheduleItem[];
    const results: Array<
      ScheduleItem & {
        _matchField?: string;
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
      if (!isAsciiQuery) return textLower.indexOf(needleLower);
      const re = new RegExp(`(^|[^a-z0-9])(${escapeRegExp(needleLower)})([^a-z0-9]|$)`, 'i');
      const m = re.exec(textLower);
      if (!m) return -1;
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

    const fieldPriOf = (field: string) => {
      if (field === 'artist') return 0;
      if (field === 'detail') return 1;
      return 2;
    };

    for (let i = 0; i < schedules.length; i++) {
      const s = schedules[i];
      if (!this.inSelectedRegion(s)) continue;
      const candidates: Array<{ field: string; raw: string }> = [
        { field: 'artist', raw: s.artist || '' },
        { field: 'detail', raw: s.detail || '' },
        { field: 'type', raw: s.type || '' },
        { field: 'locationText', raw: s.locationText || '' },
        { field: 'locationText', raw: s.displayLocation || '' },
        { field: 'venue', raw: s.venue || '' },
        { field: 'ticketPlatform', raw: s.ticketPlatform || '' }
      ];
      let field = '';
      let idx = -1;
      let fieldRaw = '';
      let bestPri = 99;
      for (let c = 0; c < candidates.length; c++) {
        const raw = candidates[c].raw;
        if (!raw) continue;
        const hit = wordBoundaryIndex(raw.toLowerCase(), qn);
        if (hit < 0) continue;
        const pri = fieldPriOf(candidates[c].field);
        if (pri < bestPri || (pri === bestPri && (idx < 0 || hit < idx))) {
          bestPri = pri;
          field = candidates[c].field;
          idx = hit;
          fieldRaw = raw;
        }
      }
      if (!field) continue;

      const key = `${s.detailUrl || ''}|${s.dateKey || ''}|${s.type || ''}|${s.artist || ''}|${s.detail || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const fieldTextLower = fieldRaw.toLowerCase();
      const exactHit =
        (fieldTextLower.trim() === qn) ||
        (isAsciiQuery && normalizeAscii(fieldRaw) === normalizeAscii(q));
      const prefixHit = fieldTextLower.trim().indexOf(qn) === 0;
      const idxNorm = idx < 0 ? 9999 : idx;
      const exactPri = exactHit ? 0 : 1;
      const wordPri = idx >= 0 ? 0 : 1;
      const prefixPri = prefixHit ? 0 : 1;
      const score = `${exactPri}|${wordPri}|${prefixPri}|${String(bestPri)}|${String(idxNorm).padStart(4, '0')}`;

      results.push({
        id: (s as any).id,
        artist: s.artist,
        type: s.type,
        date: s.date,
        dateKey: s.dateKey,
        detail: s.detail,
        ticketPlatform: s.ticketPlatform,
        ticketTime: s.ticketTime,
        venue: s.venue,
        showTime: s.showTime,
        detailUrl: s.detailUrl,
        officialUrl: (s as any).officialUrl,
        locationText: s.locationText,
        displayLocation: s.displayLocation,
        coverImage: s.coverImage,
        _matchField: field,
        _matchIndex: idx,
        _displayDetail: field === 'detail' ? makeSnippet(s.detail || '', idx) : (s.detail || ''),
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
      venue: item.venue,
      showTime: item.showTime,
      detailUrl: item.detailUrl,
      officialUrl: (item as any).officialUrl,
      locationText: item.displayLocation || item.locationText,
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
    if (hasRemoteApi()) {
      getCalendarEvents(year, month)
        .then((res) => {
          const incoming = (res.schedules || []).map((item, i) => hydrateSchedule(item, i));
          if (!incoming.length) return;
          const byId: Record<string, ScheduleItem> = {};
          const cur = this.data.schedules as ScheduleItem[];
          for (let i = 0; i < cur.length; i++) byId[String(cur[i].id)] = cur[i];
          for (let i = 0; i < incoming.length; i++) byId[String(incoming[i].id)] = incoming[i];
          const merged: ScheduleItem[] = [];
          Object.keys(byId).forEach((k) => merged.push(byId[k]));
          this.setData({ schedules: merged }, () => {
            this.buildCalendar();
            this.buildUpcomingOverview();
          });
        })
        .catch(() => {
          /* 保留已有本地/已拉取数据 */
        });
    }
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
      const base = (schedules as ScheduleItem[]).filter(s => this.inSelectedRegion(s));
      // 需求：全部 tab 不展示「活动」卡片（活动只在「活动」tab 里看）
      if (filterType === '全部') return base.filter(s => s.type !== '活动');
      if (filterType === '签售') return base.filter(s => s.type === '签售' && s.ticketPlatform === 'Ktown4u');
      return base.filter(s => s.type === filterType);
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
    let list = (schedules as ScheduleItem[]).filter(
      s => s.dateKey === selectedDateKey && this.inSelectedRegion(s)
    );
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
        venue: s.venue,
        showTime: s.showTime,
        detailUrl: s.detailUrl,
        officialUrl: (s as any).officialUrl,
        locationText: s.locationText,
        displayLocation: s.displayLocation,
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
    this.buildUpcomingOverview();
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
    // 点日期即在下方展开当日日程
    this.setData({ selectedDateKey: dateKey, dayPanelOpen: true });
    this.updateSelectedDaySchedules();
  },

  onDayPanelToggle() {
    this.setData({ dayPanelOpen: !this.data.dayPanelOpen });
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
      venue: item.venue,
      showTime: item.showTime,
      detailUrl: item.detailUrl,
      officialUrl: (item as any).officialUrl,
      locationText: item.displayLocation || item.locationText,
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

    const exists = records.some((it) => this.makeKey(it) === key);
    if (exists) {
      const next = records.filter((it) => this.makeKey(it) !== key);
      try {
        wx.setStorageSync(RECORDS_KEY, next);
      } catch (_) {}
      wx.showToast({ title: '已移出行程', icon: 'none' });
      this.updateSelectedDaySchedules();
      return;
    }

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
      venue: item.venue,
      showTime: item.showTime,
      detailUrl: item.detailUrl,
      officialUrl: (item as any).officialUrl,
      locationText: item.displayLocation || item.locationText,
      coverImage: item.coverImage,
      note: '',
      recordedAt: time
    };
    let next = [record].concat(records);
    if (next.length > 300) next = next.slice(0, 300);
    try {
      wx.setStorageSync(RECORDS_KEY, next);
    } catch (_) {}
    wx.showToast({ title: '已加入行程', icon: 'none' });
    this.updateSelectedDaySchedules();
  },


  normalizeDate(dateStr: string): string {
    if (!dateStr) return '';
    const y = new Date().getFullYear();
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
    if (/^\d{2}-\d{2}$/.test(dateStr)) return `${y}-${dateStr}`;
    return '';
  },

  /** 优先从 API 拉取；失败或未配置时用本地 data/*.js，保证页面能开 */
  loadLocalData() {
    if (hasRemoteApi()) {
      getEvents()
        .then((rows) => {
          if (!rows || rows.length === 0) {
            this.loadLocalDataFallback();
            return;
          }
          const list = rows.map((item, i) => hydrateSchedule(item, i));
          this.setData({ schedules: list }, () => {
            this.buildCalendar();
            this.buildUpcomingOverview();
          });
        })
        .catch(() => {
          this.loadLocalDataFallback();
        });
      return;
    }
    this.loadLocalDataFallback();
  },

  loadLocalDataFallback() {
    const list: ScheduleItem[] = [];
    let id = 0;
    const push = (
      item: ScheduleItem & {
        ticketPlatform?: string;
        ticketTime?: string;
        venue?: string;
        showTime?: string;
        detailUrl?: string;
        officialUrl?: string;
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
        detail: localizeReleaseDetail(item.detail || '回归'),
        ticketPlatform: item.ticketPlatform,
        ...decoratePlace(item),
        showTime: item.showTime,
        detailUrl: item.detailUrl,
        officialUrl: (item as any).officialUrl,
        coverImage: item.coverImage
      });
    };
    try {
      const comebacks = require('../../data/comebacks.js') as ScheduleItem[];
      if (Array.isArray(comebacks) && comebacks.length > 0) comebacks.forEach(item => push(item));
    } catch (_) {}
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
    this.setData({ schedules: list }, () => {
      this.buildCalendar();
      this.buildUpcomingOverview();
    });
  }
});
