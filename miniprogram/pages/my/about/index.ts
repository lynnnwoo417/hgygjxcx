// pages/my/about/index.ts
Page({
  data: {},

  onCopy() {
    // 你可以把这里替换成你的邮箱/微信号
    wx.setClipboardData({
      data: 'contact: (replace-me)',
      success: () => wx.showToast({ title: '已复制', icon: 'none' })
    });
  },

  onPolicy() {
    wx.showModal({
      title: '隐私说明（简版）',
      content:
        '本小程序默认不接入服务器：收藏/历史/资料等数据保存在你的手机本地 storage。\n\n如后续接入微信云或自建服务器，会在此处补充说明。',
      showCancel: false
    });
  }
});

