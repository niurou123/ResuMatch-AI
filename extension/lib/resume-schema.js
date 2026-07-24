// 简历结构化Schema — 适配网申全场景（学习自AI-Resume-Form-Filling-Assistant）
(function(){'use strict';
if(window.ResumeSchema)return;

// 下拉选项别名组（用于智能选项匹配）
const SELECT_ALIASES=[
  {v:['男','male','man','m']},{v:['女','female','woman','f']},
  {v:['本科','bachelor','undergraduate','学士']},{v:['硕士','master','masters','研究生','硕士研究生']},
  {v:['博士','phd','doctorate','博士研究生']},{v:['大专','associate']},{v:['高中','highschool']},
  {v:['全职','fulltime','full-time']},{v:['实习','internship','intern']},{v:['兼职','parttime']},
  {v:['是','yes','true','1']},{v:['否','no','false','0']},
  {v:['身份证','identitycard','idcard']},{v:['护照','passport']},
  {v:['未婚','single']},{v:['已婚','married']},
  {v:['中共党员','党员','中国共产党党员']},{v:['共青团员','团员','中国共青团员']},
  {v:['群众','普通群众']},{v:['中共预备党员','预备党员']},
  {v:['全日制','统招','统招全日制','fulltimedegree']},{v:['非全日制','非统招','在职']},
  {v:['汉族']},{v:['英语','english']},{v:['流利','fluent']},{v:['母语','native']},
  {v:['CET-4','四级','英语四级','cet4']},{v:['CET-6','六级','英语六级','cet6']},
];

// 完整简历分区（14个分区）
const SECTIONS=[
  {key:'personal',label:'基本信息',type:'group',fields:[
    {key:'fullName',label:'姓名',input:'text'},{key:'gender',label:'性别',input:'select',options:['','男','女']},
    {key:'birthDate',label:'出生日期',input:'date'},{key:'age',label:'年龄',input:'text'},
    {key:'email',label:'邮箱',input:'email'},{key:'phone',label:'手机号',input:'tel'},
    {key:'wechat',label:'微信号',input:'text'},{key:'currentCity',label:'现居城市',input:'text'},
    {key:'nationality',label:'民族',input:'text',placeholder:'汉族'},
    {key:'politicalStatus',label:'政治面貌',input:'text',placeholder:'共青团员'},
    {key:'maritalStatus',label:'婚姻状况',input:'select',options:['','未婚','已婚']},
    {key:'idType',label:'证件类型',input:'select',options:['','身份证','护照']},
    {key:'idNumber',label:'证件号码',input:'text'},
    {key:'summary',label:'个人简介',input:'textarea'},
  ]},
  {key:'education',label:'教育经历',type:'list',slots:3,itemLabel:'教育',fields:[
    {key:'school',label:'学校',input:'text'},{key:'degree',label:'学历',input:'select',options:['','本科','硕士','博士','大专','高中']},
    {key:'educationType',label:'学历类型',input:'select',options:['','全日制','非全日制','海外留学']},
    {key:'major',label:'专业',input:'text'},{key:'college',label:'学院',input:'text'},
    {key:'startDate',label:'入学时间',input:'date'},{key:'endDate',label:'毕业时间',input:'date'},
    {key:'graduationStatus',label:'毕业状态',input:'select',options:['','已毕业','预计毕业','在读']},
    {key:'gpa',label:'GPA',input:'text'},{key:'ranking',label:'排名',input:'text'},
    {key:'cet4',label:'英语四级',input:'text'},{key:'cet6',label:'英语六级',input:'text'},
    {key:'courses',label:'主修课程',input:'textarea'},
  ]},
  {key:'internships',label:'实习经历',type:'list',slots:3,itemLabel:'实习',fields:[
    {key:'company',label:'公司',input:'text'},{key:'title',label:'岗位',input:'text'},
    {key:'startDate',label:'开始时间',input:'date'},{key:'endDate',label:'结束时间',input:'date'},
    {key:'description',label:'工作内容',input:'textarea'},{key:'achievements',label:'成果',input:'textarea'},
    {key:'technologies',label:'技术栈',input:'textarea'},
  ]},
  {key:'projects',label:'项目经历',type:'list',slots:4,itemLabel:'项目',fields:[
    {key:'name',label:'项目名称',input:'text'},{key:'role',label:'角色',input:'text'},
    {key:'organization',label:'所属组织',input:'text'},
    {key:'startDate',label:'开始时间',input:'date'},{key:'endDate',label:'结束时间',input:'date'},
    {key:'description',label:'项目描述',input:'textarea'},{key:'highlights',label:'项目亮点',input:'textarea'},
    {key:'technologies',label:'技术栈',input:'textarea'},
  ]},
  {key:'skills',label:'技能',type:'group',fields:[
    {key:'programmingLanguages',label:'编程语言',input:'textarea'},
    {key:'frameworks',label:'框架',input:'textarea'},{key:'databases',label:'数据库',input:'textarea'},
    {key:'aiTools',label:'AI工具',input:'textarea'},{key:'cloudPlatforms',label:'云平台',input:'textarea'},
    {key:'tooling',label:'工程工具',input:'textarea'},{key:'domainKnowledge',label:'行业经验',input:'textarea'},
  ]},
  {key:'jobPreferences',label:'求职偏好',type:'group',fields:[
    {key:'targetRole',label:'目标岗位',input:'text'},{key:'targetIndustry',label:'目标行业',input:'text'},
    {key:'expectedCity',label:'期望城市',input:'text'},{key:'expectedSalary',label:'期望薪资',input:'text'},
    {key:'availableDate',label:'可入职日期',input:'date'},
    {key:'employmentType',label:'期望用工类型',input:'select',options:['','全职','实习','兼职']},
    {key:'willingToRelocate',label:'是否接受异地',input:'select',options:['','是','否']},
  ]},
  {key:'additional',label:'补充信息',type:'group',fields:[
    {key:'awards',label:'获奖荣誉',input:'textarea'},{key:'publications',label:'论文发表',input:'textarea'},
    {key:'competitions',label:'竞赛经历',input:'textarea'},{key:'languages',label:'语言能力',input:'textarea'},
    {key:'certificates',label:'证书认证',input:'textarea'},{key:'customNotes',label:'其他备注',input:'textarea'},
  ]},
];

// 工具函数
function createEmptyProfile(){
  const p={};
  SECTIONS.forEach(s=>{
    if(s.type==='group'){p[s.key]={};s.fields.forEach(f=>{p[s.key][f.key]='';});}
    else{p[s.key]=[];for(let i=0;i<(s.slots||1);i++){const item={};s.fields.forEach(f=>{item[f.key]='';});p[s.key].push(item);}}
  });
  return p;
}

function getValue(obj,path){
  return path.split('.').reduce((o,k)=>(o&&o[k]!==undefined)?o[k]:'',obj);
}

function matchSelectOption(options,value){
  if(!value||!options||!options.length)return'';
  const clean=s=>String(s||'').toLowerCase().replace(/\s+/g,'').replace(/[()（）]/g,'');
  const v=clean(value);if(!v)return'';
  // 精确匹配
  const exact=options.find(o=>clean(o)===v);if(exact)return exact;
  // 别名展开匹配
  for(const group of SELECT_ALIASES){
    if(group.v.some(a=>clean(a)===v)){
      for(const alias of group.v){const m=options.find(o=>clean(o)===clean(alias));if(m)return m;}
    }
  }
  // 包含匹配
  const contain=options.find(o=>clean(o).includes(v)||v.includes(clean(o)));if(contain)return contain;
  // 模糊匹配
  let best='',bs=0;options.forEach(o=>{if(!o)return;const s=[...v].filter(c=>clean(o).includes(c)).length/v.length;if(s>bs&&s>=0.4){bs=s;best=o;}});
  return best;
}

window.ResumeSchema={SECTIONS,SELECT_ALIASES,createEmptyProfile,getValue,matchSelectOption,version:2};
})();
