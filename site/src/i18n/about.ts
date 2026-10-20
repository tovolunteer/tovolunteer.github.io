const ONT = 'https://www.ontario.ca/page/get-your-high-school-volunteer-hours';
const TDSB = 'https://www.tdsb.on.ca/High-School/Going-to-High-School/Beyond-8/Community-Involvement';
const SUGGEST = 'https://forms.gle/yZb7DKi738pddq2TA';
const REPORT = 'https://docs.google.com/forms/d/e/1FAIpQLSdLaNO3c7fHfeCD8C29ZKxT5Berbx6g0HisKFY6xK9YeEmDsw/viewform';

export type AboutSection = { title: string; paras?: string[]; bullets?: string[]; links?: { label: string; href: string }[] };

export const about: Record<'en' | 'zh', AboutSection[]> = {
  en: [
    { title: 'What this site is', paras: [
      'Toronto Volunteer Hub is an unofficial, non-profit community project. It gathers publicly posted volunteer opportunities around Toronto — with a focus on tree planting and the environment — plus food banks, so they are easier to find in one place.',
      'We are not affiliated with the City of Toronto, any school board, or the organizations listed.' ] },
    { title: 'Where the information comes from', bullets: [
      'Happening Soon: events are read automatically from the organizations’ public web pages (currently TRCA and LEAF) twice a day.',
      'Plan Ahead, food banks and the directory: maintained by hand. Each card shows when it was last verified and links to its sources.',
      'Age, registration and hours-documentation details are shown only when the organization’s own page says so. Otherwise they read “Not stated”.',
      'Chinese titles are machine-translated and checked by software; the English original is always linked.' ] },
    { title: 'Always confirm on the official site', paras: [
      'Dates, spaces and requirements change — events can fill up or be cancelled because of weather. Before you go, open the original page, sign up there if needed, and follow the organizer’s safety instructions.' ] },
    { title: 'Ontario 40-hour community involvement', paras: [
      'High school students need 40 hours of community involvement to earn the Ontario Secondary School Diploma. Key points from the official pages:' ],
      bullets: [
        'Hours can start in the summer after Grade 8.',
        'Activities can happen during breaks, spares and other non-instructional time.',
        'You cannot replace a worker who would normally be paid, or be paid yourself.',
        'Your role should not involve operating a vehicle, power tools or scaffolding, giving medication or medical procedures, or handling designated substances.',
        'If an activity is not on your school board’s approved list, get your principal’s approval first.',
        'Your school decides what counts — check with your guidance office.' ],
      links: [ { label: 'Ontario.ca — Get your high school volunteer hours', href: ONT }, { label: 'TDSB — Community Involvement', href: TDSB } ] },
    { title: 'Carpooling', paras: [
      'We plan to help volunteers going to the same event find each other through a Discord group (adults 18+ only). The site will never arrange rides or handle payments; drivers are not verified.' ] },
    { title: 'Suggest or correct something', paras: [ 'Know an opportunity we are missing, or spotted a mistake? Let us know — no account needed.' ],
      links: [ { label: 'Suggest an opportunity', href: SUGGEST }, { label: 'Report a problem', href: REPORT } ] },
  ],
  zh: [
    { title: '这个网站是什么', paras: [
      'Toronto Volunteer Hub 是一个非官方、非营利的社区项目。我们把多伦多公开发布的志愿机会（以植树和环保为主）和食物银行信息集中在一处，方便查找。',
      '本站与多伦多市政府、任何教育局或所列机构均无隶属关系。' ] },
    { title: '信息从哪里来', bullets: [
      '近期活动：每天两次自动读取机构的公开网页（目前为 TRCA 和 LEAF）。',
      '长期项目、食物银行和机构列表：人工维护，每张卡片都写明最后核实日期并附来源链接。',
      '年龄、报名和时长证明信息，只有机构官网明确写了才显示，否则显示「未注明」。',
      '中文标题由机器翻译并经程序核对，每条都附英文原文链接。' ] },
    { title: '请以官网为准', paras: [
      '日期、名额和要求随时会变，活动可能满员或因天气取消。出发前请打开原文页面，需要报名的在官网报名，并遵守主办方的安全要求。' ] },
    { title: '安省高中 40 小时社区服务', paras: [
      '安省高中生毕业（OSSD）需要完成 40 小时社区服务。官方页面的要点：' ],
      bullets: [
        '8 年级结束后的暑假就可以开始累计。',
        '可以在课间、空课等非上课时间进行。',
        '不能顶替通常有薪水的工作人员，自己也不能领报酬。',
        '不能操作车辆、电动工具或脚手架，不能给药或做医疗操作，不能接触指定危险物质。',
        '活动不在教育局认可清单上的，要先获得校长批准。',
        '具体是否算时长由学校决定，请向学校辅导处确认。' ],
      links: [ { label: 'Ontario.ca — 高中志愿时长（英文）', href: ONT }, { label: 'TDSB — 社区服务（英文）', href: TDSB } ] },
    { title: '拼车', paras: [
      '我们计划通过 Discord 群帮助去同一个活动的志愿者互相联系（仅限 18 岁以上）。本站不安排行程、不经手任何费用，也不审核司机。' ] },
    { title: '推荐或纠错', paras: [ '知道我们漏掉的机会，或发现错误？告诉我们，无需注册账号。' ],
      links: [ { label: '推荐一个活动', href: SUGGEST }, { label: '报告错误', href: REPORT } ] },
  ],
};
