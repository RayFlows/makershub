// pages/email_bind/email_bind.js

const defaultConfig = require('../../config.js');
const {
  USER_PROFILE_KEY,
  checkTokenValidity,
  fetchAndStoreUserProfile,
  getUserProfile,
} = require('../index/index.js');

/**
 * 获取认证接口配置。
 *
 * 旧缓存里可能只有部分 auth 配置，所以这里用新版默认配置兜底合并。
 */
function getAuthConfig() {
  const cachedConfig = wx.getStorageSync('config') || {};
  return {
    ...(defaultConfig.auth || {}),
    ...(cachedConfig.auth || {}),
  };
}

/**
 * 规范化邮箱输入。
 */
function normalizeEmail(email) {
  return (email || '').trim().toLowerCase();
}

/**
 * 校验邮箱格式。
 */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

Page({
  data: {
    email: '',
    code: '',
    currentEmail: '',
    hasBoundEmail: false,
    isEmailFocused: false,
    isCodeFocused: false,
    isSending: false,
    isBinding: false,
    countdown: 0,
    devCode: '',
  },

  onLoad() {
    console.log('[EmailBind] 页面加载');
    this.loadUserProfileFromCache();
  },

  onShow() {
    console.log('[EmailBind] 页面显示');
    this.loadUserProfileFromCache();
  },

  onUnload() {
    this.clearCountdownTimer();
  },

  /**
   * 从缓存加载当前用户邮箱绑定状态。
   */
  loadUserProfileFromCache() {
    console.log('[EmailBind] 从缓存加载用户信息');

    const cachedProfile = getUserProfile() || {};
    const currentEmail = cachedProfile.email || '';

    this.setData({
      currentEmail,
      hasBoundEmail: !!currentEmail,
      email: currentEmail || this.data.email,
    });
  },

  /**
   * 更新邮箱输入。
   */
  updateEmail(e) {
    this.setData({
      email: e.detail.value,
      devCode: '',
    });
  },

  /**
   * 更新验证码输入。
   */
  updateCode(e) {
    this.setData({
      code: e.detail.value,
    });
  },

  onEmailFocused() {
    this.setData({ isEmailFocused: true });
  },

  onEmailBlur() {
    this.setData({ isEmailFocused: false });
  },

  onCodeFocused() {
    this.setData({ isCodeFocused: true });
  },

  onCodeBlur() {
    this.setData({ isCodeFocused: false });
  },

  /**
   * 发送绑定邮箱验证码。
   */
  sendEmailCode() {
    const email = normalizeEmail(this.data.email);
    if (!this.validateEmailBeforeSubmit(email)) return;
    if (this.data.isSending || this.data.countdown > 0) return;

    console.log('[EmailBind] 开始发送邮箱验证码');
    this.setData({ isSending: true });

    checkTokenValidity()
      .then((token) => {
        const authConfig = getAuthConfig();
        wx.request({
          url: authConfig.emailSendCode,
          method: 'POST',
          data: {
            email,
            purpose: 'bind_email',
          },
          header: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          success: (res) => {
            console.log('[EmailBind] 验证码发送响应:', res.data);
            if (res.statusCode === 200 && res.data.success && res.data.data) {
              const devCode = res.data.data.dev_code || '';
              this.setData({
                email: res.data.data.email || email,
                code: devCode || this.data.code,
                devCode,
              });
              this.startCountdown(60);
              wx.showToast({
                title: devCode ? '本地验证码已填入' : '验证码已发送',
                icon: 'none',
              });
            } else {
              this.showRequestError(res.data, '发送失败');
            }
          },
          fail: (err) => {
            console.error('[EmailBind] 发送验证码请求失败:', err);
            wx.showToast({ title: '网络异常,请重试', icon: 'none' });
          },
          complete: () => {
            this.setData({ isSending: false });
          },
        });
      })
      .catch((err) => {
        console.warn('[EmailBind] 令牌校验失败:', err);
        this.setData({ isSending: false });
        wx.showToast({ title: '请先完成微信登录', icon: 'none' });
      });
  },

  /**
   * 使用验证码绑定邮箱。
   */
  bindEmail() {
    const email = normalizeEmail(this.data.email);
    const code = (this.data.code || '').trim();
    if (!this.validateEmailBeforeSubmit(email)) return;
    if (!/^\d{6}$/.test(code)) {
      wx.showToast({ title: '请输入6位验证码', icon: 'none' });
      return;
    }
    if (this.data.isBinding) return;

    console.log('[EmailBind] 开始绑定邮箱');
    this.setData({ isBinding: true });

    checkTokenValidity()
      .then((token) => {
        const authConfig = getAuthConfig();
        wx.request({
          url: authConfig.emailBind,
          method: 'POST',
          data: { email, code },
          header: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          success: (res) => {
            console.log('[EmailBind] 邮箱绑定响应:', res.data);
            if (res.statusCode === 200 && res.data.success && res.data.data) {
              this.saveBoundEmailToCache(res.data.data);
              fetchAndStoreUserProfile(token);
              wx.showToast({ title: '绑定成功', icon: 'success' });
              setTimeout(() => {
                wx.navigateBack({ delta: 1 });
              }, 1200);
            } else {
              this.showRequestError(res.data, '绑定失败');
            }
          },
          fail: (err) => {
            console.error('[EmailBind] 绑定邮箱请求失败:', err);
            wx.showToast({ title: '网络异常,请重试', icon: 'none' });
          },
          complete: () => {
            this.setData({ isBinding: false });
          },
        });
      })
      .catch((err) => {
        console.warn('[EmailBind] 令牌校验失败:', err);
        this.setData({ isBinding: false });
        wx.showToast({ title: '请先完成微信登录', icon: 'none' });
      });
  },

  /**
   * 绑定成功后更新本地用户缓存。
   */
  saveBoundEmailToCache(bindResult) {
    const cachedProfile = getUserProfile() || {};
    const user = bindResult.user || {};
    const updatedProfile = {
      ...cachedProfile,
      id: user.id || cachedProfile.id,
      real_name: user.display_name || cachedProfile.real_name,
      profile_photo: user.avatar_url || cachedProfile.profile_photo,
      status: user.status || cachedProfile.status,
      email: bindResult.email || user.email || cachedProfile.email,
    };

    wx.setStorageSync(USER_PROFILE_KEY, updatedProfile);
    this.setData({
      currentEmail: updatedProfile.email,
      hasBoundEmail: !!updatedProfile.email,
      email: updatedProfile.email,
    });
    console.log('[EmailBind] 邮箱绑定缓存已更新:', updatedProfile);
  },

  /**
   * 发送验证码后的倒计时。
   */
  startCountdown(seconds) {
    this.clearCountdownTimer();
    this.setData({ countdown: seconds });

    this.countdownTimer = setInterval(() => {
      const next = this.data.countdown - 1;
      if (next <= 0) {
        this.clearCountdownTimer();
        this.setData({ countdown: 0 });
        return;
      }
      this.setData({ countdown: next });
    }, 1000);
  },

  /**
   * 清理倒计时定时器。
   */
  clearCountdownTimer() {
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = null;
    }
  },

  /**
   * 发送和绑定前统一校验邮箱。
   */
  validateEmailBeforeSubmit(email) {
    if (!email) {
      wx.showToast({ title: '请输入邮箱', icon: 'none' });
      return false;
    }
    if (!isValidEmail(email)) {
      wx.showToast({ title: '邮箱格式不正确', icon: 'none' });
      return false;
    }
    return true;
  },

  /**
   * 展示后端业务错误。
   */
  showRequestError(data, fallbackMessage) {
    const error = data && data.error ? data.error : {};
    const title = error.message || fallbackMessage;
    console.warn('[EmailBind] 请求返回错误:', data);
    wx.showToast({
      title,
      icon: 'none',
      duration: 2500,
    });
  },

  handlerGobackClick() {
    wx.navigateBack({ delta: 1 });
  },
});
