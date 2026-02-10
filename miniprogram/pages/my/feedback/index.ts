// pages/my/feedback/index.ts
const FEEDBACK_EMAIL = 'Iynnnwoo417@gmail.com';

Page({
  data: {
    email: FEEDBACK_EMAIL
  },

  onCopyEmail() {
    wx.setClipboardData({
      data: FEEDBACK_EMAIL,
      success: () => wx.showToast({ title: '邮箱已复制', icon: 'none' })
    });
  },

  onCopyTemplate() {
    const now = new Date();
    const time = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
      now.getDate()
    ).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const subject = `KPOP小程序产品优化反馈 ${time}`;
    const body = `[产品优化] ${time}\n（请填写你的反馈内容）`;
    const payload = `To: ${FEEDBACK_EMAIL}\nSubject: ${subject}\n\n${body}`;
    wx.setClipboardData({
      data: payload,
      success: () => {
        wx.showModal({
          title: '已复制邮件模板',
          content: `请打开邮箱，收件人填写：${FEEDBACK_EMAIL}\\n并粘贴模板后编辑发送。`,
          showCancel: false
        });
      }
    });
  }
});

