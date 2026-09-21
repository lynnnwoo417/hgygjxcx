/// <reference path="./types/index.d.ts" />

interface IAppOption {
  globalData: {
    userInfo?: WechatMiniprogram.UserInfo,
    eventDetail?: {
      id: number;
      artist: string;
      type: string;
      date: string;
      dateKey: string;
      detail: string;
      ticketPlatform?: string;
      ticketTime?: string;
      venue?: string;
      showTime?: string;
      detailUrl?: string;
      officialUrl?: string;
      locationText?: string;
      coverImage?: string;
    },
  }
  userInfoReadyCallback?: WechatMiniprogram.GetUserInfoSuccessCallback,
}