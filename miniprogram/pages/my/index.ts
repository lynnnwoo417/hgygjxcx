// pages/my/index.ts
type MyProfile = {
  nickname: string;
  avatarUrl: string;
};

const STORAGE_KEYS = {
  profile: 'my_profile',
  favorites: 'my_favorites',
  reminders: 'my_reminders',
  history: 'my_history'
};

function safeGetArray(key: string): any[] {
  try {
    const v = wx.getStorageSync(key);
    return Array.isArray(v) ? v : [];
  } catch (_) {
    return [];
  }
}

function safeGetProfile(): MyProfile | null {
  try {
    const v = wx.getStorageSync(STORAGE_KEYS.profile) as any;
    if (v && typeof v.nickname === 'string' && typeof v.avatarUrl === 'string') return v as MyProfile;
    return null;
  } catch (_) {
    return null;
  }
}

Page({
  data: {
    profile: null as MyProfile | null,
    stats: {
      favorites: 0,
      reminders: 0,
      history: 0
    },
    // 可选：展示存储占用（粗略）
    storageInfo: '' as string
  },

  onLoad() {
    this.refresh();
  },

  onShow() {
    // 从子页面返回时刷新
    this.refresh();
  },

  refresh() {
    const profile = safeGetProfile();
    const favorites = safeGetArray(STORAGE_KEYS.favorites).length;
    const reminders = safeGetArray(STORAGE_KEYS.reminders).length;
    const history = safeGetArray(STORAGE_KEYS.history).length;

    let storageInfo = '';
    try {
      const info = wx.getStorageInfoSync();
      storageInfo = `本地存储：${info.currentSize}KB / ${info.limitSize}KB`;
    } catch (_) {}

    this.setData({
      profile,
      stats: { favorites, reminders, history },
      storageInfo
    });
  },

  onTapLogin() {
    // 没有微信云/后端时，先用“本地资料”模拟一个主流 App 的登录态
    // 后续你接微信云/自建后端时，这里替换成真正授权登录即可
    const existed = safeGetProfile();
    if (existed) {
      wx.showToast({ title: '已登录', icon: 'none' });
      return;
    }
    const profile: MyProfile = {
      nickname: '游客用户',
      avatarUrl:
        'https://mmocgame.qpic.cn/wechatgame/0/0' // 占位，避免空头像（也可以换成本地图片）
    };
    try {
      wx.setStorageSync(STORAGE_KEYS.profile, profile);
    } catch (_) {}
    this.refresh();
    wx.showToast({ title: '已在本机创建资料', icon: 'none' });
  },

  onTapEditProfile() {
    const profile = safeGetProfile();
    if (!profile) {
      wx.showToast({ title: '请先点击登录', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '修改昵称',
      editable: true,
      placeholderText: profile.nickname,
      success: (res) => {
        if (!res.confirm) return;
        const text = (res.content || '').trim();
        const next: MyProfile = { nickname: text || profile.nickname, avatarUrl: profile.avatarUrl };
        try {
          wx.setStorageSync(STORAGE_KEYS.profile, next);
        } catch (_) {}
        this.refresh();
      }
    });
  },

  onNav(e: WechatMiniprogram.TouchEvent) {
    const to = (e.currentTarget.dataset.to as string) || '';
    if (!to) return;
    wx.navigateTo({ url: to });
  },

  onExportData() {
    const payload = {
      v: 1,
      profile: safeGetProfile(),
      favorites: safeGetArray(STORAGE_KEYS.favorites),
      reminders: safeGetArray(STORAGE_KEYS.reminders),
      history: safeGetArray(STORAGE_KEYS.history)
    };
    const text = JSON.stringify(payload);
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制到剪贴板', icon: 'none' })
    });
  },

  onImportData() {
    wx.showModal({
      title: '导入数据',
      content: '请在弹窗中粘贴你之前导出的 JSON（会覆盖本机数据）。',
      confirmText: '继续',
      success: (r) => {
        if (!r.confirm) return;
        wx.showModal({
          title: '粘贴 JSON',
          editable: true,
          placeholderText: '{"v":1,...}',
          success: (res) => {
            if (!res.confirm) return;
            try {
              const obj = JSON.parse((res.content || '').trim());
              if (!obj || obj.v !== 1) throw new Error('bad');
              wx.setStorageSync(STORAGE_KEYS.profile, obj.profile || '');
              wx.setStorageSync(STORAGE_KEYS.favorites, Array.isArray(obj.favorites) ? obj.favorites : []);
              wx.setStorageSync(STORAGE_KEYS.reminders, Array.isArray(obj.reminders) ? obj.reminders : []);
              wx.setStorageSync(STORAGE_KEYS.history, Array.isArray(obj.history) ? obj.history : []);
              this.refresh();
              wx.showToast({ title: '导入成功', icon: 'none' });
            } catch (_) {
              wx.showToast({ title: 'JSON 格式不正确', icon: 'none' });
            }
          }
        });
      }
    });
  },

  onClearLocal() {
    wx.showModal({
      title: '清理本地数据',
      content: '将清空收藏/提醒/历史/个人资料（仅本机）。确认继续？',
      confirmText: '清空',
      success: (res) => {
        if (!res.confirm) return;
        try {
          wx.removeStorageSync(STORAGE_KEYS.profile);
          wx.removeStorageSync(STORAGE_KEYS.favorites);
          wx.removeStorageSync(STORAGE_KEYS.reminders);
          wx.removeStorageSync(STORAGE_KEYS.history);
        } catch (_) {}
        this.refresh();
        wx.showToast({ title: '已清理', icon: 'none' });
      }
    });
  }
});

