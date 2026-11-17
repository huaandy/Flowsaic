import { useEffect, useRef, useState } from 'react'

type Page = 'Dashboard' | 'Degree Progress' | 'Course Catalog' | 'Semester Planner' | 'My Calendar' | 'Create Schedule' | 'AI Advisor' | 'Advisor Dashboard' | 'My Profile' | 'Scheduling Preferences' | 'Settings' | 'Help & Support'

const nav: { label: Page; icon: string }[] = [
  { label: 'Dashboard', icon: 'grid' },
  { label: 'Degree Progress', icon: 'chart' },
  { label: 'Course Catalog', icon: 'book' },
  { label: 'Semester Planner', icon: 'layers' },
  { label: 'My Calendar', icon: 'calendar' },
  { label: 'Create Schedule', icon: 'spark' },
  { label: 'AI Advisor', icon: 'chat' },
]

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5v13Z"/><path d="M8 8h8"/></>,
    layers: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    spark: <><path d="m12 3-1.6 4.4L6 9l4.4 1.6L12 15l1.6-4.4L18 9l-4.4-1.6L12 3Z"/><path d="m5 15-.8 2.2L2 18l2.2.8L5 21l.8-2.2L8 18l-2.2-.8L5 15Z"/></>,
    chat: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z"/><path d="M8 9h8M8 13h5"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    arrow: <path d="m9 18 6-6-6-6"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    sliders: <><path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h8M16 18h4"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="14" cy="18" r="2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.6 2.6 0 1 1 4.4 1.9c-1.1.8-2 1.2-2 2.6M12 18h.01"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></>,
    eye: <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/></>,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{paths[name]}</svg>
}

type ScheduleStatus = 'Draft Saved' | 'Pending Approval' | 'Approved'
type EventCategory = 'Academic'|'Work'|'Personal / Study'|'Extracurricular'
type CalendarEvent = { id:string; day:'Mon'|'Tue'|'Wed'|'Thu'|'Fri'; time:string; endTime:string; title:string; meta:string; tone:string; type:'Class'|'Personal commitment'; category:EventCategory; recurrence:'None'|'Weekly'; priority:'Low'|'Normal'|'High'; fixed:boolean; readOnly:boolean }
type ScheduleMeeting = { day:number; start:number; end:number }
type CourseSection = { id:string; schedule:string; instructor:string; room:string; meetings:ScheduleMeeting[]; seats:number; rating:number; reviews:number }
type CourseRecord = {
  code:string
  name:string
  subject:string
  credits:number
  tone:string
  prerequisite:string
  prerequisiteStatus:'Completed'|'In Progress'|'Not Required'
  concurrentAllowed:boolean
  level:'200'|'300'|'400'
  delivery:'Face-to-face'|'Hybrid'|'Online'
  days:string
  description:string
  requirement:string
  sections:CourseSection[]
}
type PlannedTerms = Record<string,string[]>
type StudentProfile = { name:string; email:string; university:string; major:string; minor:string; degree:string; standing:string; graduation:string; photo:string }
type SchedulingPreferences = { time:string; days:string[]; minCredits:number; maxCredits:number; delivery:string[]; distance:string; minRating:number; flexibility:'Flexible'|'Balanced'|'Strict' }
type AppSettings = { emailNotifications:boolean; pushNotifications:boolean; advisorUpdates:boolean; scheduleAlerts:boolean; appearance:'Light'|'Dark'|'System'; highContrast:boolean; largerText:boolean; reduceMotion:boolean; profileVisibility:'Private'|'Advisors only'|'University community' }

const courseCatalog:CourseRecord[] = [
  {code:'CS 410',name:'Human–Computer Interaction',subject:'Computer Science',credits:3,tone:'blue',prerequisite:'CS 301',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'400',delivery:'Hybrid',days:'Mon/Wed',requirement:'Computer Science Core',description:'Design and evaluate interactive systems through user research, prototyping, accessibility testing, and a semester-long product studio.',sections:[
    {id:'001',schedule:'Mon/Wed · 10:00–11:15 AM',instructor:'Prof. Maya Patel',room:'Innovation Lab 204',meetings:[{day:0,start:10,end:11.25},{day:2,start:10,end:11.25}],seats:8,rating:4.8,reviews:42},
    {id:'002',schedule:'Tue/Thu · 3:00–4:15 PM',instructor:'Prof. Aaron Brooks',room:'Innovation Lab 118',meetings:[{day:1,start:15,end:16.25},{day:3,start:15,end:16.25}],seats:3,rating:4.5,reviews:31},
  ]},
  {code:'CS 365',name:'Database Systems',subject:'Computer Science',credits:4,tone:'purple',prerequisite:'CS 220',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'300',delivery:'Face-to-face',days:'Mon/Wed or Tue/Thu',requirement:'Computer Science Core',description:'Model relational data, write advanced SQL, and study indexing, transactions, query planning, and dependable application persistence.',sections:[
    {id:'001',schedule:'Tue/Thu · 1:30–2:45 PM',instructor:'Dr. Lena Ortiz',room:'Engineering Hall 118',meetings:[{day:1,start:13.5,end:14.75},{day:3,start:13.5,end:14.75}],seats:0,rating:4.7,reviews:58},
    {id:'002',schedule:'Mon/Wed · 8:00–9:15 AM',instructor:'Dr. Marcus Lee',room:'Engineering Hall 205',meetings:[{day:0,start:8,end:9.25},{day:2,start:8,end:9.25}],seats:11,rating:4.3,reviews:36},
  ]},
  {code:'DES 240',name:'Interaction Design',subject:'Design',credits:3,tone:'orange',prerequisite:'DES 110',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'200',delivery:'Face-to-face',days:'Mon/Wed or Tue/Thu',requirement:'Design Minor',description:'Practice interaction patterns, information architecture, prototyping, and critique while designing an end-to-end digital service.',sections:[
    {id:'001',schedule:'Mon/Wed · 2:00–3:15 PM',instructor:'Prof. Nia Williams',room:'Design Studio 3',meetings:[{day:0,start:14,end:15.25},{day:2,start:14,end:15.25}],seats:4,rating:4.9,reviews:27},
    {id:'002',schedule:'Tue/Thu · 10:30–11:45 AM',instructor:'Prof. Jonah Kim',room:'Design Studio 5',meetings:[{day:1,start:10.5,end:11.75},{day:3,start:10.5,end:11.75}],seats:9,rating:4.6,reviews:22},
  ]},
  {code:'MATH 310',name:'Discrete Mathematics II',subject:'Mathematics',credits:3,tone:'mint',prerequisite:'MATH 210',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'300',delivery:'Face-to-face',days:'Tue/Thu or Mon/Wed/Fri',requirement:'Mathematics',description:'Extend discrete structures into graph theory, combinatorics, recurrence relations, and proof techniques used in advanced computing.',sections:[
    {id:'001',schedule:'Tue/Thu · 9:00–10:15 AM',instructor:'Dr. Evelyn Chen',room:'Science Center 212',meetings:[{day:1,start:9,end:10.25},{day:3,start:9,end:10.25}],seats:6,rating:4.6,reviews:49},
    {id:'002',schedule:'Mon/Wed/Fri · 11:00–11:50 AM',instructor:'Dr. Samuel Reed',room:'Science Center 108',meetings:[{day:0,start:11,end:11.83},{day:2,start:11,end:11.83},{day:4,start:11,end:11.83}],seats:14,rating:4.2,reviews:34},
  ]},
  {code:'ECON 325',name:'Behavioral Economics',subject:'Economics',credits:3,tone:'orange',prerequisite:'ECON 210',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'300',delivery:'Hybrid',days:'Mon/Wed/Fri or Tue/Thu',requirement:'General Education',description:'Use experiments and cognitive models to examine how real decisions depart from traditional economic assumptions.',sections:[
    {id:'001',schedule:'Mon/Wed/Fri · 12:00–12:50 PM',instructor:'Dr. Sofia Ramirez',room:'Miller Hall 105',meetings:[{day:0,start:12,end:12.83},{day:2,start:12,end:12.83},{day:4,start:12,end:12.83}],seats:18,rating:4.7,reviews:61},
    {id:'002',schedule:'Tue/Thu · 2:00–3:15 PM',instructor:'Dr. Eli Warren',room:'Miller Hall 214',meetings:[{day:1,start:14,end:15.25},{day:3,start:14,end:15.25}],seats:7,rating:4.4,reviews:29},
  ]},
  {code:'ENG 330',name:'Writing for Technology',subject:'English',credits:3,tone:'blue',prerequisite:'ENG 215',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'300',delivery:'Online',days:'Asynchronous + workshop',requirement:'General Education',description:'Develop clear technical documentation, research summaries, product narratives, and audience-aware communication for technology teams.',sections:[
    {id:'001',schedule:'Tue/Thu · 4:00–5:15 PM',instructor:'Prof. Claire Bennett',room:'Online + Liberal Arts 310',meetings:[{day:1,start:16,end:17.25},{day:3,start:16,end:17.25}],seats:12,rating:4.8,reviews:44},
    {id:'002',schedule:'Mon/Wed · 4:00–5:15 PM',instructor:'Prof. David Park',room:'Online + Liberal Arts 221',meetings:[{day:0,start:16,end:17.25},{day:2,start:16,end:17.25}],seats:5,rating:4.3,reviews:25},
  ]},
  {code:'PSY 210',name:'Cognitive Psychology',subject:'Psychology',credits:3,tone:'mint',prerequisite:'PSY 101',prerequisiteStatus:'Completed',concurrentAllowed:false,level:'200',delivery:'Face-to-face',days:'Mon/Wed/Fri or Tue/Thu',requirement:'General Education',description:'Explore attention, memory, perception, language, and decision-making through classic findings and contemporary research methods.',sections:[
    {id:'001',schedule:'Mon/Wed/Fri · 1:00–1:50 PM',instructor:'Dr. Amara Jones',room:'Behavioral Sciences 104',meetings:[{day:0,start:13,end:13.83},{day:2,start:13,end:13.83},{day:4,start:13,end:13.83}],seats:21,rating:4.7,reviews:73},
    {id:'002',schedule:'Tue/Thu · 11:00 AM–12:15 PM',instructor:'Dr. Isaac Moore',room:'Behavioral Sciences 206',meetings:[{day:1,start:11,end:12.25},{day:3,start:11,end:12.25}],seats:2,rating:4.1,reviews:38},
  ]},
  {code:'CS 430',name:'Software Engineering',subject:'Computer Science',credits:4,tone:'purple',prerequisite:'CS 365',prerequisiteStatus:'In Progress',concurrentAllowed:false,level:'400',delivery:'Face-to-face',days:'Mon/Wed or Tue/Thu',requirement:'Computer Science Core',description:'Build and maintain a team software system using architecture reviews, automated testing, delivery pipelines, and iterative planning.',sections:[
    {id:'001',schedule:'Tue/Thu · 5:00–6:15 PM',instructor:'Prof. Olivia Shah',room:'Engineering Hall 302',meetings:[{day:1,start:17,end:18.25},{day:3,start:17,end:18.25}],seats:10,rating:4.6,reviews:40},
    {id:'002',schedule:'Mon/Wed · 1:00–2:15 PM',instructor:'Prof. Theo Grant',room:'Engineering Hall 307',meetings:[{day:0,start:13,end:14.25},{day:2,start:13,end:14.25}],seats:1,rating:4.4,reviews:33},
  ]},
  {code:'CS 420',name:'Machine Learning',subject:'Computer Science',credits:3,tone:'blue',prerequisite:'MATH 310',prerequisiteStatus:'In Progress',concurrentAllowed:false,level:'400',delivery:'Hybrid',days:'Tue/Thu',requirement:'Computer Science Core',description:'Implement supervised and unsupervised learning methods while evaluating model quality, bias, and practical deployment tradeoffs.',sections:[
    {id:'001',schedule:'Tue/Thu · 11:00 AM–12:15 PM',instructor:'Dr. Priya Natarajan',room:'Data Lab 220',meetings:[{day:1,start:11,end:12.25},{day:3,start:11,end:12.25}],seats:7,rating:4.8,reviews:54},
  ]},
  {code:'CS 490',name:'Senior Capstone',subject:'Computer Science',credits:4,tone:'purple',prerequisite:'CS 430',prerequisiteStatus:'In Progress',concurrentAllowed:false,level:'400',delivery:'Face-to-face',days:'Mon/Wed',requirement:'Computer Science Core',description:'Integrate the degree through a client-sponsored team project with formal discovery, implementation, testing, and public presentation.',sections:[
    {id:'001',schedule:'Mon/Wed · 2:00–3:50 PM',instructor:'Dr. Evelyn Chen',room:'Capstone Studio',meetings:[{day:0,start:14,end:15.83},{day:2,start:14,end:15.83}],seats:16,rating:4.7,reviews:45},
  ]},
  {code:'DES 340',name:'Design Research Methods',subject:'Design',credits:3,tone:'orange',prerequisite:'DES 240',prerequisiteStatus:'In Progress',concurrentAllowed:false,level:'300',delivery:'Hybrid',days:'Tue/Thu',requirement:'Design Minor',description:'Plan ethical field research, conduct interviews and observations, synthesize evidence, and translate findings into design direction.',sections:[
    {id:'001',schedule:'Tue/Thu · 12:30–1:45 PM',instructor:'Prof. Nia Williams',room:'Design Studio 2',meetings:[{day:1,start:12.5,end:13.75},{day:3,start:12.5,end:13.75}],seats:8,rating:4.9,reviews:27},
  ]},
]

const currentTermCourses=['CS 301','ECON 210','DES 240','MATH 260','ENG 215']
const completedTermName='Spring 2025'
const currentTermName='Fall 2025'
const completedCourseCodes=new Set(['CS 101','CS 201','CS 220','CS 250','CS 270','CS 280','MATH 210','MATH 220','MATH 240','MATH 250','DES 110','DES 120','ENG 101','ENG 102','PSY 101','HIST 110','BIO 105','COMM 120','SOC 101','ART 100','STAT 200','PHIL 210','SCI 115','CIV 100'])
const initialPlannedTerms:PlannedTerms={
  [completedTermName]:['CS 220','MATH 240','DES 120','ENG 102'],
  [currentTermName]:currentTermCourses,
  'Spring 2026':['CS 410','CS 365','MATH 310','ENG 330'],
  'Summer 2026':['CS 430'],
  'Fall 2026':['CS 490','CS 420','DES 340'],
}
const officialStudentProfile:Omit<StudentProfile,'photo'>={name:'Maya Johnson',email:'mjohnson@muleriders.saumag.edu',university:'Southern Arkansas University',major:'Computer Science',minor:'Design',degree:'B.S. Computer Science',standing:'Good academic standing',graduation:'December 2026'}

const initialCalendarEvents: CalendarEvent[] = [
  { id:'cs301-mon', day:'Mon', time:'9:00 AM', endTime:'10:15 AM', title:'CS 301 · Algorithms', meta:'Engineering Hall 201', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'study-mon', day:'Mon', time:'11:30 AM', endTime:'12:30 PM', title:'Study group', meta:'Library · Room 4B', tone:'purple', type:'Personal commitment', category:'Personal / Study', recurrence:'Weekly', priority:'Normal', fixed:false, readOnly:false },
  { id:'econ210-mon', day:'Mon', time:'2:00 PM', endTime:'3:15 PM', title:'ECON 210 · Macroeconomics', meta:'Miller Hall 105', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'club-mon', day:'Mon', time:'5:30 PM', endTime:'7:00 PM', title:'Campus design club', meta:'Student Center', tone:'mint', type:'Personal commitment', category:'Extracurricular', recurrence:'Weekly', priority:'Normal', fixed:true, readOnly:false },
  { id:'des240-tue', day:'Tue', time:'10:30 AM', endTime:'11:45 AM', title:'DES 240 · Interaction Design', meta:'Design Studio 3', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'work-tue', day:'Tue', time:'3:00 PM', endTime:'6:00 PM', title:'Work shift', meta:'Student Services', tone:'orange', type:'Personal commitment', category:'Work', recurrence:'Weekly', priority:'High', fixed:true, readOnly:false },
  { id:'cs301-wed', day:'Wed', time:'9:00 AM', endTime:'10:15 AM', title:'CS 301 · Algorithms', meta:'Engineering Hall 201', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'econ210-wed', day:'Wed', time:'2:00 PM', endTime:'3:15 PM', title:'ECON 210 · Macroeconomics', meta:'Miller Hall 105', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'des240-thu', day:'Thu', time:'10:30 AM', endTime:'11:45 AM', title:'DES 240 · Interaction Design', meta:'Design Studio 3', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'club-thu', day:'Thu', time:'5:30 PM', endTime:'7:00 PM', title:'Campus design club', meta:'Student Center', tone:'mint', type:'Personal commitment', category:'Extracurricular', recurrence:'Weekly', priority:'Normal', fixed:true, readOnly:false },
  { id:'cs301-fri', day:'Fri', time:'9:00 AM', endTime:'10:15 AM', title:'CS 301 · Algorithms', meta:'Engineering Hall 201', tone:'blue', type:'Class', category:'Academic', recurrence:'Weekly', priority:'High', fixed:true, readOnly:true },
  { id:'study-fri', day:'Fri', time:'1:00 PM', endTime:'2:00 PM', title:'Study group', meta:'Library · Room 4B', tone:'purple', type:'Personal commitment', category:'Personal / Study', recurrence:'Weekly', priority:'Normal', fixed:false, readOnly:false },
]

function Dashboard({ go,calendarEvents,onAddEvent,scheduleStatus,askFlow,viewSchedule,studentName }: { go:(p:Page)=>void;calendarEvents:CalendarEvent[];onAddEvent:(event:CalendarEvent)=>void;scheduleStatus:ScheduleStatus;askFlow:(question:string)=>void;viewSchedule:()=>void;studentName:string }) {
  const [scheduleView, setScheduleView] = useState<'day' | 'week'>('day')
  const [eventDialogOpen, setEventDialogOpen] = useState(false)
  const [newEvent, setNewEvent] = useState({ title: '', time: '12:00', location: '' })
  const [flowQuestion,setFlowQuestion]=useState('')
  const currentCourses = [
    { code: 'CS 301', name: 'Algorithms', credits: 3, tone: 'blue' },
    { code: 'ECON 210', name: 'Macroeconomics', credits: 3, tone: 'orange' },
    { code: 'DES 240', name: 'Interaction Design', credits: 3, tone: 'purple' },
    { code: 'MATH 260', name: 'Linear Algebra', credits: 3, tone: 'mint' },
    { code: 'ENG 215', name: 'Academic Writing', credits: 3, tone: 'blue' },
  ]
  const scheduleNextStep=scheduleStatus==='Approved'?'Ready for registration':scheduleStatus==='Pending Approval'?'Advisor review in progress':'Next: review conflicts and submit'
  const timeValue=(time:string)=>{
    const [clock,period]=time.split(' ')
    const [hourText,minuteText]=clock.split(':')
    let hour=Number(hourText)%12
    if(period==='PM') hour+=12
    return hour*60+Number(minuteText)
  }
  const todayEvents=calendarEvents.filter(event=>event.day==='Mon').sort((first,second)=>timeValue(first.time)-timeValue(second.time))
  const weekSchedule=(['Mon','Tue','Wed','Thu','Fri'] as CalendarEvent['day'][]).map((day,index)=>({day,date:String(14+index),items:calendarEvents.filter(event=>event.day===day).sort((first,second)=>timeValue(first.time)-timeValue(second.time))}))
  const addEvent = () => {
    if (!newEvent.title.trim()) return
    const [hours, minutes] = newEvent.time.split(':').map(Number)
    const time = new Date(2000, 0, 1, hours, minutes).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    onAddEvent({
      id:`dashboard-${Date.now()}`,
      day:'Mon',
      time,
      endTime:new Date(2000,0,1,hours+1,minutes).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'}),
      title: newEvent.title.trim(),
      meta: newEvent.location.trim() || 'Personal commitment',
      tone: 'purple',
      type:'Personal commitment',
      category:'Personal / Study',
      recurrence:'None',
      priority:'Normal',
      fixed:false,
      readOnly:false,
    })
    setNewEvent({ title: '', time: '12:00', location: '' })
    setEventDialogOpen(false)
    setScheduleView('day')
  }
  const submitFlowQuestion=()=>{
    if(!flowQuestion.trim()) return
    askFlow(flowQuestion.trim())
    setFlowQuestion('')
  }
  return <>
    <section className="hero">
      <div><span className="eyebrow dashboard-date">MONDAY, OCTOBER 14</span><h1>Good morning, {studentName.split(' ')[0]}.</h1><p>You're on track. Here's what your day looks like.</p></div>
      <button className="primary" onClick={() => go('Create Schedule')}><Icon name="spark"/> Create schedule</button>
    </section>
    <div className="stats-grid">
      <article className="card progress-card degree-progress-card">
        <div className="card-head"><h2 className="module-title"><span className="feature-icon blue"><Icon name="chart" size={17}/></span>Degree Progress</h2><span className="pill success dashboard-status">On track</span></div>
        <div className="degree-completion-summary"><strong>68%</strong><span>Degree completion</span></div>
        <div className="bar"><i style={{width:'68%'}}/></div>
        <p className="credit-summary"><strong>82 of 120 credits completed</strong><span> · 38 remaining</span></p>
        <div className="degree-projection"><span className="degree-projection-icon"><Icon name="calendar" size={18}/></span><div><span>Expected graduation</span><strong>December 2026</strong><p>3 semesters remaining</p></div></div>
        <button className="text-btn degree-progress-link" onClick={() => go('Degree Progress')}>View degree progress <Icon name="arrow" size={15}/></button>
      </article>
      <article className="card semester-card">
        <div className="semester-head">
          <div><span className="label current-semester-label"><span className="feature-icon purple"><Icon name="layers" size={16}/></span>Current semester</span><h2>Fall 2025</h2></div>
          <span className="semester-total"><strong>15</strong> credits</span>
        </div>
        <div className="semester-courses">
          {currentCourses.map(course => <div className="semester-course" key={course.code}>
            <i className={course.tone}/>
            <span className="semester-code">{course.code}</span>
            <strong className="semester-course-name">{course.name}</strong>
            <span className="course-credits">{course.credits} cr</span>
          </div>)}
        </div>
        <button className="text-btn semester-plan-link" onClick={() => go('Semester Planner')}>View semester plan <Icon name="arrow" size={15}/></button>
        <div className="semester-schedule-status"><div className="semester-schedule-copy"><span>Spring 2026 Schedule</span><strong className={`schedule-status-${scheduleStatus.toLowerCase().replace(' ','-')}`}>{scheduleStatus}</strong><small>{scheduleNextStep}</small></div><button onClick={viewSchedule}>{scheduleStatus==='Draft Saved'?'Continue':'View schedule'} <Icon name="arrow" size={14}/></button></div>
      </article>
    </div>
    <article className="ai-card dashboard-insight ask-flow-card"><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon"/><div className="insight-copy"><h3>Ask Flow</h3><span className="ask-flow-support">Get personalized academic guidance</span><p>You’re ready for CS 410, and Flow can help compare sections, review requirements, or fit courses around your commitments.</p><form className="ask-flow-form" onSubmit={event=>{event.preventDefault();submitFlowQuestion()}}><input value={flowQuestion} onChange={event=>setFlowQuestion(event.target.value)} placeholder="Ask Flow about your academic plan..."/><button type="submit"><Icon name="chat" size={16}/> Ask Flow</button></form><div className="ask-flow-prompts"><button onClick={()=>askFlow('Am I on track to graduate in December 2026?')}>Am I on track?</button><button onClick={()=>askFlow('What courses should I take next semester?')}>What should I take next?</button><button onClick={()=>askFlow('Build a balanced Spring 2026 schedule around my commitments.')}>Build my schedule</button></div></div></article>
    <div className="dashboard-main">
      <article className="card schedule-card">
        <div className="section-head schedule-head"><div><h2 className="schedule-title module-title"><span className="feature-icon teal"><Icon name="calendar" size={17}/></span>{scheduleView === 'day' ? 'Today’s schedule' : 'This week'}</h2><p className="schedule-summary">{scheduleView === 'day' ? `${todayEvents.length} commitments · Next at ${todayEvents[0]?.time||'—'}` : `${calendarEvents.length} commitments · October 14–18`}</p></div><div className="schedule-actions"><div className="view-tabs"><button className={scheduleView === 'day' ? 'active' : ''} onClick={() => setScheduleView('day')}>Day</button><button className={scheduleView === 'week' ? 'active' : ''} onClick={() => setScheduleView('week')}>Week</button></div><button className="ghost add-event-button" onClick={() => setEventDialogOpen(true)}><Icon name="plus" size={15}/> Add event</button><button className="ghost" onClick={() => go('My Calendar')}>View calendar</button></div></div>
        {scheduleView === 'day'
          ? <div className="timeline">{todayEvents.map((e,i)=><button className="event" key={e.id} onClick={()=>alert(`${e.title}\n${e.time} · ${e.meta}\n${e.type}`)}><span className={`event-time ${i===0?'primary-event-time':'selected-event-time'}`}>{e.time}</span><i className={`event-dot ${e.tone}`}/><span className="event-copy"><strong className="selected-event-title">{e.title}</strong><small className="selected-event-meta">{e.meta}</small></span>{i===0&&<span className="pill live dashboard-live-pill">In 24 min</span>}<Icon name="arrow" size={16}/></button>)}</div>
          : <div className="dashboard-week">{weekSchedule.map((day, index) => <div className={`dashboard-day ${index === 0 ? 'today' : ''}`} key={day.day}><div className="dashboard-day-head"><span>{day.day}</span><strong>{day.date}</strong><small>{day.items.length} events</small></div><div className="dashboard-day-events">{day.items.map(item => <button key={item.id} onClick={() => alert(`${item.title}\n${item.time} · ${item.meta}\n${item.type}`)}><i className={item.tone}/><span><small>{item.time}</small><strong>{item.title}</strong></span></button>)}</div></div>)}</div>}
      </article>
    </div>
    {eventDialogOpen&&<div className="modal-backdrop" onMouseDown={() => setEventDialogOpen(false)}><form className="event-dialog" onMouseDown={event => event.stopPropagation()} onSubmit={event => { event.preventDefault(); addEvent() }}><div className="event-dialog-head"><div><span className="eyebrow">NEW COMMITMENT</span><h2>Add an event</h2><p>Add work, activities, appointments, or anything else you need to attend.</p></div></div><label>Event name<input autoFocus required value={newEvent.title} onChange={event => setNewEvent({...newEvent, title: event.target.value})} placeholder="e.g. Career fair"/></label><div className="event-dialog-row"><label>Time<input required type="time" value={newEvent.time} onChange={event => setNewEvent({...newEvent, time: event.target.value})}/></label><label>Location or details<input value={newEvent.location} onChange={event => setNewEvent({...newEvent, location: event.target.value})} placeholder="e.g. Student Center"/></label></div><div className="event-dialog-actions"><button type="button" className="ghost" onClick={() => setEventDialogOpen(false)}>Cancel</button><button className="primary" type="submit"><Icon name="plus" size={15}/> Add to schedule</button></div></form></div>}
  </>
}

function DegreePage({plannedTerms,openCatalog,addToPlan,askFlow}:{plannedTerms:PlannedTerms;openCatalog:(code:string)=>void;addToPlan:(code:string)=>void;askFlow:(question:string)=>void}) {
  const [expanded,setExpanded]=useState<string[]>([])
  const [auditOpen,setAuditOpen]=useState(false)
  const plannedCodes=new Set(Object.entries(plannedTerms).filter(([term])=>term!==completedTermName&&term!==currentTermName).flatMap(([,courses])=>courses))
  const names:Record<string,string>={CS101:'Programming Foundations',CS201:'Data Structures',CS220:'Computer Architecture',CS250:'Systems Programming',CS270:'Theory of Computation',CS280:'Web Development',CS301:'Algorithms',MATH210:'Discrete Mathematics I',MATH220:'Calculus II',MATH240:'Linear Algebra',MATH250:'Probability',DES110:'Design Foundations',DES120:'Visual Communication',DES240:'Interaction Design',DES360:'Information Architecture',DES410:'Design Systems',ENG101:'Academic Composition',ENG102:'Research Writing',ECON210:'Macroeconomics',ENG215:'Academic Writing'}
  const groups=[
    {name:'Computer Science Core',tone:'blue',required:10,courses:['CS 101','CS 201','CS 220','CS 250','CS 270','CS 280','CS 301','CS 365','CS 410','CS 430']},
    {name:'Mathematics',tone:'purple',required:5,courses:['MATH 210','MATH 220','MATH 240','MATH 250','MATH 310']},
    {name:'General Education',tone:'orange',required:12,courses:['ENG 101','ENG 102','HIST 110','BIO 105','COMM 120','SOC 101','ART 100','STAT 200','PHIL 210','ECON 210','ENG 215','ENG 330']},
    {name:'Design Minor',tone:'mint',required:6,courses:['DES 110','DES 120','DES 240','DES 340','DES 360','DES 410']},
  ]
  const statusFor=(code:string)=>completedCourseCodes.has(code)?'Completed':currentTermCourses.includes(code)?'In progress':plannedCodes.has(code)?'Planned':'Remaining'
  const knownCourse=(code:string)=>courseCatalog.find(course=>course.code===code)
  const courseName=(code:string)=>knownCourse(code)?.name||names[code.replace(' ','')]||'Degree requirement'
  const completedCredits=82
  const inProgressCredits=(plannedTerms[currentTermName]||[]).reduce((total,code)=>total+(knownCourse(code)?.credits||3),0)
  const plannedCredits=Object.entries(plannedTerms).filter(([term])=>term!==completedTermName&&term!==currentTermName).flatMap(([,courses])=>courses).reduce((total,code)=>total+(knownCourse(code)?.credits||3),0)
  const projectedCredits=Math.min(120,completedCredits+inProgressCredits+plannedCredits)
  const latestTerm=Object.entries(plannedTerms).filter(([term,courses])=>term!==completedTermName&&courses.length).at(-1)?.[0]||'Not yet projected'
  const graduation=latestTerm.startsWith('Fall')?`December ${latestTerm.slice(-4)}`:latestTerm.startsWith('Spring')?`May ${latestTerm.slice(-4)}`:`August ${latestTerm.slice(-4)}`
  return <>
    <div className="degree-summary-strip card">
      <div><span>Official record</span><strong>82 / 120 credits</strong><small>Confirmed by the registrar</small></div>
      <div><span>Planned progress</span><strong>{projectedCredits} / 120 credits</strong><small>Estimate based on your roadmap</small></div>
      <div><span>Projected graduation</span><strong>{graduation}</strong><small className="estimate-label">Estimate · updates with your plan</small></div>
    </div>
    <div className="degree-layout">
      <article className="card degree-requirements">
        <div className="section-head degree-section-head"><div><h2 className="module-title"><span className="feature-icon green"><Icon name="check" size={17}/></span>Requirement groups</h2><p>Southern Arkansas University · B.S. Computer Science · Design minor</p></div><span className="pill success">On track</span></div>
        {groups.map(group=>{const satisfied=group.courses.filter(code=>statusFor(code)==='Completed').length;const inProgress=group.courses.filter(code=>statusFor(code)==='In progress').length;const planned=group.courses.filter(code=>statusFor(code)==='Planned').length;const remaining=group.courses.filter(code=>statusFor(code)==='Remaining').length;const percent=Math.round(((satisfied+inProgress*.65+planned*.35)/group.required)*100);const isExpanded=expanded.includes(group.name);return <section className={`audit-group ${isExpanded?'expanded':''}`} key={group.name}>
          <button className="requirement-summary" onClick={()=>setExpanded(current=>current.includes(group.name)?current.filter(name=>name!==group.name):[...current,group.name])}>
            <span className={`soft-icon ${group.tone}`}><Icon name={group.name==='Computer Science Core'?'book':'check'}/></span>
            <span className="requirement-copy"><strong>{group.name}</strong><small>{satisfied} completed · {inProgress} in progress · {planned} planned · {remaining} remaining</small></span>
            <span className="req-progress"><b>{Math.min(percent,100)}%</b><span className="bar"><i style={{width:`${Math.min(percent,100)}%`}}/></span></span>
            <span className={`disclosure ${isExpanded?'open':''}`}><Icon name="arrow" size={17}/></span>
          </button>
          {isExpanded&&<div className="requirement-details">{group.courses.map(code=>{const status=statusFor(code);const course=knownCourse(code);return <div className="audit-course" key={code}><span className={`audit-status ${status.toLowerCase().replace(' ','-')}`}><Icon name={status==='Completed'?'check':status==='Remaining'?'plus':'calendar'} size={14}/></span><span><strong>{code} · {courseName(code)}</strong><small>{course?.credits||3} credits · {course?.prerequisite&&course.prerequisite!=='None'?`Prerequisite: ${course.prerequisite}`:'No outstanding prerequisite'}</small></span><em className={`record-label ${status.toLowerCase().replace(' ','-')}`}>{status}</em>{status==='Remaining'&&<span className="audit-actions"><button onClick={()=>openCatalog(code)}>View course</button><button onClick={()=>addToPlan(code)}>Add to plan</button></span>}</div>})}</div>}
        </section>})}
      </article>
      <aside className="degree-side">
        <article className="card projection degree-projection-card"><span className="eyebrow">GRADUATION PROJECTION</span><h2>{graduation}</h2><p>Official credits, current enrollment, and the {plannedCredits}-credit future roadmap remain separate in this estimate.</p><div className="projection-meter"><div className="bar"><i style={{width:`${projectedCredits/120*100}%`}}/></div><span><b>{projectedCredits}</b> projected credits</span></div><div className="projection-legend"><span><i className="confirmed"/>82 completed</span><span><i className="in-progress"/>{inProgressCredits} in progress</span><span><i className="estimated"/>{plannedCredits} planned</span></div><button className="primary wide" onClick={()=>setAuditOpen(true)}>View detailed audit</button></article>
        <article className="ai-card builder-ai-insight degree-ai-insight"><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon"/><div><span className="eyebrow">AI INSIGHT</span><h3>Need degree guidance?</h3><p>Review requirements, course sequencing, and graduation timing.</p><button onClick={()=>askFlow('Review my degree requirements and tell me what I should prioritize next.')}><Icon name="chat" size={15}/> Ask Flow</button></div></article>
      </aside>
    </div>
    {auditOpen&&<div className="modal-backdrop" onMouseDown={()=>setAuditOpen(false)}><section className="event-dialog degree-audit-dialog" onMouseDown={event=>event.stopPropagation()}><div className="audit-dialog-head"><div><span className="eyebrow">DETAILED DEGREE AUDIT</span><h2>B.S. Computer Science</h2><p>Official completion is based only on posted academic records. In-progress and planned courses remain estimates until successful completion.</p></div><button className="ghost square-button" onClick={()=>setAuditOpen(false)}>×</button></div><div className="audit-summary-grid"><span><b>82</b> completed credits</span><span><b>{inProgressCredits}</b> in-progress credits</span><span><b>{plannedCredits}</b> planned credits</span><span><b>{groups.flatMap(group=>group.courses).filter(code=>statusFor(code)==='Remaining').length}</b> remaining courses</span></div>{groups.map(group=><div className="audit-dialog-group" key={group.name}><strong>{group.name}</strong><span>{group.courses.filter(code=>statusFor(code)==='Completed').length} fulfilled · {group.courses.filter(code=>statusFor(code)!=='Completed').length} outstanding or planned</span></div>)}</section></div>}
  </>
}

function Catalog({focusCode='',plannedTerms,togglePlan,openSchedule,calendarEvents}:{focusCode?:string;plannedTerms:PlannedTerms;togglePlan:(code:string)=>void;openSchedule:(code:string)=>void;calendarEvents:CalendarEvent[]}) {
  const [query,setQuery]=useState(focusCode)
  const [filtersOpen,setFiltersOpen]=useState(false)
  const [expanded,setExpanded]=useState(focusCode)
  const [department,setDepartment]=useState('All departments')
  const [level,setLevel]=useState('All levels')
  const [credits,setCredits]=useState('Any credits')
  const [prerequisite,setPrerequisite]=useState('Any prerequisite')
  const [delivery,setDelivery]=useState('Any format')
  const [days,setDays]=useState('Any days')
  const [availability,setAvailability]=useState('Any availability')
  const [ratings,setRatings]=useState<Record<string,{rating:number;count:number}>>({})
  const [ratingDraft,setRatingDraft]=useState<Record<string,number>>({})
  const plannedCodes=new Set(Object.entries(plannedTerms).filter(([term])=>term!==completedTermName&&term!==currentTermName).flatMap(([,courses])=>courses))
  const [proposedSections]=useState<Record<string,string>>(()=>{
    try {
      return JSON.parse(localStorage.getItem('flowsaic-schedule-draft')||'{}').selectedSections||{}
    } catch {
      return {}
    }
  })
  const toHour=(time:string)=>{const [clock,period]=time.split(' ');const [hours,minutes]=clock.split(':').map(Number);return (hours%12)+(period==='PM'?12:0)+minutes/60}
  const dayIndex:Record<CalendarEvent['day'],number>={Mon:0,Tue:1,Wed:2,Thu:3,Fri:4}
  const overlaps=(first:ScheduleMeeting,second:ScheduleMeeting)=>first.day===second.day&&first.start<second.end&&second.start<first.end
  const conflictsWithCalendar=(course:CourseRecord,events:CalendarEvent[])=>course.sections.every(section=>section.meetings.some(meeting=>events.some(event=>dayIndex[event.day]===meeting.day&&toHour(event.time)<meeting.end&&meeting.start<toHour(event.endTime))))
  const conflictsWithProposal=(course:CourseRecord)=>{const proposedMeetings=Object.entries(proposedSections).filter(([code])=>code!==course.code).flatMap(([code,sectionId])=>{const proposedCourse=courseCatalog.find(item=>item.code===code);return proposedCourse?.sections.find(section=>section.id===sectionId)?.meetings||[]});return proposedMeetings.length>0&&course.sections.every(section=>section.meetings.some(meeting=>proposedMeetings.some(proposed=>overlaps(meeting,proposed))))}
  const visible=courseCatalog.filter(course=>{
    const searchable=`${course.code} ${course.name} ${course.subject} ${course.description}`.toLowerCase()
    return searchable.includes(query.toLowerCase())
      &&(department==='All departments'||course.subject===department)
      &&(level==='All levels'||course.level===level)
      &&(credits==='Any credits'||course.credits===Number(credits))
      &&(prerequisite==='Any prerequisite'||(prerequisite==='Eligible now'?course.prerequisiteStatus!=='In Progress':course.prerequisiteStatus==='In Progress'))
      &&(delivery==='Any format'||course.delivery===delivery)
      &&(days==='Any days'||course.days.includes(days))
      &&(availability==='Any availability'||(availability==='Open sections'?course.sections.some(section=>section.seats>0):course.sections.some(section=>section.seats===0)))
  })
  const departments=Array.from(new Set(courseCatalog.map(course=>course.subject)))
  const submitRating=(course:CourseRecord)=>{const value=ratingDraft[course.code];if(!value)return;const current=ratings[course.code]||{rating:course.sections[0].rating,count:course.sections[0].reviews};setRatings({...ratings,[course.code]:{rating:(current.rating*current.count+value)/(current.count+1),count:current.count+1}});setRatingDraft({...ratingDraft,[course.code]:0})}
  return <>
    <div className="catalog-tools card"><div className="searchbar"><Icon name="search"/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search by course, subject, or keyword…"/><button onClick={()=>setFiltersOpen(value=>!value)}>Filters {filtersOpen?'−':'+'}</button></div>{filtersOpen&&<div className="catalog-filters"><label>Department<select value={department} onChange={event=>setDepartment(event.target.value)}><option>All departments</option>{departments.map(value=><option key={value}>{value}</option>)}</select></label><label>Level<select value={level} onChange={event=>setLevel(event.target.value)}><option>All levels</option><option>200</option><option>300</option><option>400</option></select></label><label>Credits<select value={credits} onChange={event=>setCredits(event.target.value)}><option>Any credits</option><option value="3">3 credits</option><option value="4">4 credits</option></select></label><label>Prerequisites<select value={prerequisite} onChange={event=>setPrerequisite(event.target.value)}><option>Any prerequisite</option><option>Eligible now</option><option>Unmet prerequisite</option></select></label><label>Delivery<select value={delivery} onChange={event=>setDelivery(event.target.value)}><option>Any format</option><option>Face-to-face</option><option>Hybrid</option><option>Online</option></select></label><label>Days<select value={days} onChange={event=>setDays(event.target.value)}><option>Any days</option><option>Mon/Wed</option><option>Tue/Thu</option><option>Mon/Wed/Fri</option></select></label><label>Availability<select value={availability} onChange={event=>setAvailability(event.target.value)}><option>Any availability</option><option>Open sections</option><option>Waitlist possible</option></select></label><button className="ghost clear-filters" onClick={()=>{setDepartment('All departments');setLevel('All levels');setCredits('Any credits');setPrerequisite('Any prerequisite');setDelivery('Any format');setDays('Any days');setAvailability('Any availability')}}>Clear filters</button></div>}</div>
    <div className="catalog-results-head"><span>{visible.length} courses</span><small>Eligibility uses confirmed records. Conflict labels separate enrolled classes, commitments, and proposed sections.</small></div>
    <div className="catalog-grid">{visible.map(course=>{const isExpanded=expanded===course.code;const eligible=course.prerequisiteStatus!=='In Progress';const enrolledConflict=conflictsWithCalendar(course,calendarEvents.filter(event=>event.type==='Class'));const commitmentConflict=conflictsWithCalendar(course,calendarEvents.filter(event=>event.type==='Personal commitment'));const proposalConflict=conflictsWithProposal(course);const plannedSemester=Object.entries(plannedTerms).find(([term,courses])=>term!==completedTermName&&term!==currentTermName&&courses.includes(course.code))?.[0];const planned=Boolean(plannedSemester);const rating=ratings[course.code]||{rating:course.sections.reduce((total,section)=>total+section.rating*section.reviews,0)/course.sections.reduce((total,section)=>total+section.reviews,0),count:course.sections.reduce((total,section)=>total+section.reviews,0)};return <article className={`card course catalog-course ${course.code===focusCode?'focused-course':''} ${!eligible?'course-ineligible':''} ${enrolledConflict?'course-enrolled-conflict':''} ${proposalConflict?'course-proposal-conflict':''}`} key={course.code}>
      <div className="catalog-course-top"><span className="course-code">{course.code}</span><span className="catalog-badges"><span className="pill">{course.credits} credits</span><span className={`eligibility ${eligible?'eligible':'ineligible'}`}>{eligible?'Eligible':'Prerequisite needed'}</span></span></div>
      <h2>{course.name}</h2><p>{course.description}</p>
      <div className="course-meta-row"><span>{course.subject} · {course.level}-level</span><span>{course.delivery}</span></div>
      <div className="professor-rating"><span className="stars">★</span><strong>{rating.rating.toFixed(1)}</strong><span>{rating.count} student reviews</span></div>
      <div className="course-status-stack">{!eligible&&<span className="course-status prerequisite-status"><Icon name="book" size={14}/>Complete {course.prerequisite} before enrolling</span>}{enrolledConflict&&<span className="course-status enrolled-conflict"><Icon name="calendar" size={14}/>Conflicts with an enrolled class</span>}{proposalConflict&&<span className="course-status proposal-conflict"><Icon name="layers" size={14}/>Conflicts with the proposed schedule</span>}{commitmentConflict&&<span className="course-status commitment-conflict"><Icon name="calendar" size={14}/>Conflicts with a personal commitment</span>}{eligible&&!enrolledConflict&&!proposalConflict&&!commitmentConflict&&<span className="course-status eligible-status"><Icon name="check" size={14}/>Prerequisites confirmed · no known conflicts</span>}</div>
      <div className="course-foot"><button className="course-detail-button" onClick={()=>setExpanded(isExpanded?'':course.code)}>{isExpanded?'Hide details':'Course details'} <Icon name="arrow" size={14}/></button><span className="catalog-plan-action">{plannedSemester&&<small>Planned · {plannedSemester}</small>}<button disabled={!eligible} className={planned?'ghost':'primary'} onClick={()=>togglePlan(course.code)}>{planned?'Remove from plan':'Add to plan'}</button></span></div>
      {isExpanded&&<div className="course-detail-panel"><div className="detail-facts"><span><b>Requirement</b>{course.requirement}</span><span><b>Prerequisite</b>{course.prerequisite}</span><span><b>Typical days</b>{course.days}</span></div><h3>Available sections</h3>{course.sections.map(section=><div className="catalog-section" key={section.id}><div><strong>Section {section.id} · {section.schedule}</strong><span>{section.instructor} · {section.room}</span></div><div className="section-rating"><span>★ {section.rating}</span><small>{section.reviews} reviews</small></div><span className={section.seats?'seats-open':'seats-full'}>{section.seats?`${section.seats} seats`:'Waitlist'}</span></div>)}<div className="rating-form"><span>Rate this course</span><div>{[1,2,3,4,5].map(value=><button className={(ratingDraft[course.code]||0)>=value?'selected':''} key={value} onClick={()=>setRatingDraft({...ratingDraft,[course.code]:value})}>★</button>)}</div><button className="ghost" disabled={!ratingDraft[course.code]} onClick={()=>submitRating(course)}>Submit rating</button></div><button className="schedule-section-link" disabled={!eligible} onClick={()=>openSchedule(course.code)}>Select a section in Create Schedule <Icon name="arrow" size={14}/></button></div>}
    </article>})}</div>
    {!visible.length&&<div className="card catalog-empty"><Icon name="search"/><strong>No courses match these filters</strong><span>Clear one or more filters to broaden the results.</span></div>}
  </>
}

function Planner({plannedTerms,setPlannedTerms,openCatalog,openSchedule,askFlow,preferences}:{plannedTerms:PlannedTerms;setPlannedTerms:(terms:PlannedTerms)=>void;openCatalog:(code:string)=>void;openSchedule:(codes:string[],term:string)=>void;askFlow:(question:string)=>void;preferences:SchedulingPreferences}) {
  const [detailCode,setDetailCode]=useState('')
  const termNames=Object.keys(plannedTerms)
  const termCredits=(term:string)=>plannedTerms[term].reduce((total,code)=>total+(courseCatalog.find(course=>course.code===code)?.credits||3),0)
  const futureTerms=Object.entries(plannedTerms).filter(([term,courses])=>term!==completedTermName&&term!==currentTermName&&courses.length)
  const latestPlannedTerm=futureTerms.at(-1)?.[0]||'Not projected'
  const projectedGraduation=latestPlannedTerm.startsWith('Fall')?`December ${latestPlannedTerm.slice(-4)}`:latestPlannedTerm.startsWith('Spring')?`May ${latestPlannedTerm.slice(-4)}`:latestPlannedTerm.startsWith('Summer')?`August ${latestPlannedTerm.slice(-4)}`:'Not projected'
  const futureCredits=futureTerms.flatMap(([,courses])=>courses).reduce((total,code)=>total+(courseCatalog.find(course=>course.code===code)?.credits||3),0)
  const moveCourse=(code:string,from:string,to:string)=>{if(from===to||from===completedTermName||to===completedTermName)return;setPlannedTerms({...plannedTerms,[from]:plannedTerms[from].filter(item=>item!==code),[to]:[...plannedTerms[to].filter(item=>item!==code),code]})}
  const removeCourse=(code:string,term:string)=>setPlannedTerms({...plannedTerms,[term]:plannedTerms[term].filter(item=>item!==code)})
  const addTerm=()=>{const options=['Summer 2026','Fall 2026','Spring 2027','Fall 2027'];const next=options.find(term=>!plannedTerms[term]);if(next)setPlannedTerms({...plannedTerms,[next]:[]})}
  const prerequisiteWarning=(code:string,termIndex:number)=>{const course=courseCatalog.find(item=>item.code===code);if(!course||course.prerequisite==='None'||completedCourseCodes.has(course.prerequisite)||currentTermCourses.includes(course.prerequisite))return '';const earlier=termNames.slice(0,termIndex).some(term=>plannedTerms[term].includes(course.prerequisite));return earlier?'':`Complete ${course.prerequisite} first`}
  return <>
    <div className="planner-toolbar card"><div><strong>Academic roadmap</strong><span>{futureCredits} future credits · Target {preferences.minCredits}–{preferences.maxCredits} per term · Projected {projectedGraduation}</span></div><div><button className="ghost" onClick={()=>askFlow('Review my semester roadmap for prerequisites, workload, and graduation timing.')}><Icon name="chat" size={15}/> Ask Flow</button><button className="ghost" onClick={addTerm}><Icon name="plus" size={15}/> Add future semester</button></div></div>
    <div className="term-grid planner-term-grid">{termNames.map((term,termIndex)=>{const credits=termCredits(term);const status=term===completedTermName?'completed':term===currentTermName?'current':'planned';const warnings=status==='planned'?plannedTerms[term].map(code=>prerequisiteWarning(code,termIndex)).filter(Boolean):[];return <article className={`term card planner-term ${status}`} key={term} onDragOver={event=>event.preventDefault()} onDrop={event=>{const [code,from]=event.dataTransfer.getData('text/plain').split('|');if(code&&from)moveCourse(code,from,term)}}>
      <div className="planner-term-head"><div><span className={`term-status ${status}`}>{status==='current'?'Current term':status==='completed'?'Completed':'Planned'}</span><h2>{term}</h2></div><span className={`credit-total ${credits>preferences.maxCredits?'overload':''}`}>{credits} credits</span></div>
      {status==='planned'&&credits>preferences.maxCredits&&<div className="term-warning"><Icon name="calendar" size={14}/>Above your {preferences.maxCredits}-credit preference</div>}
      {status==='planned'&&!term.startsWith('Summer')&&credits>0&&credits<preferences.minCredits&&<div className="term-warning"><Icon name="calendar" size={14}/>Below your {preferences.minCredits}-credit preference</div>}
      {warnings.length>0&&<div className="term-warning"><Icon name="book" size={14}/><span>{warnings[0]}</span><button onClick={()=>openCatalog(warnings[0].replace('Complete ','').replace(' first',''))}>Review</button></div>}
      <div className="planner-course-list">{plannedTerms[term].map(code=>{const course=courseCatalog.find(item=>item.code===code);const warning=status==='planned'?prerequisiteWarning(code,termIndex):'';return <div className={`course-chip planner-course-chip ${warning?'has-warning':''}`} draggable={status==='planned'} onDragStart={event=>event.dataTransfer.setData('text/plain',`${code}|${term}`)} key={code}><i className={course?.tone||'blue'}/><button className="planner-course-main" onClick={()=>setDetailCode(code)}><strong>{code}</strong><small>{course?.name||'Recorded coursework'}</small></button><span className="planner-course-actions">{status==='planned'&&<><select aria-label={`Move ${code}`} value={term} onChange={event=>moveCourse(code,term,event.target.value)}>{termNames.filter(name=>name!==completedTermName).map(name=><option key={name}>{name}</option>)}</select><button aria-label={`Remove ${code}`} onClick={()=>removeCourse(code,term)}>×</button><span className="drag">••</span></>}</span></div>})}</div>
      {status!=='completed'&&<button className="add-course" onClick={()=>openCatalog('')}><Icon name="plus"/> Add course</button>}
      {status==='planned'&&plannedTerms[term].length>0&&<button className="term-schedule-button" onClick={()=>openSchedule(plannedTerms[term],term)}>Send to Create Schedule <Icon name="arrow" size={14}/></button>}
    </article>})}</div>
    {!Object.values(plannedTerms).flat().includes('CS 490')&&<div className="planner-wide-warning"><Icon name="book" size={17}/><span><strong>Capstone is not yet planned.</strong> Add CS 490 after CS 430 to preserve your graduation timeline.</span></div>}
    {detailCode&&<div className="modal-backdrop" onMouseDown={()=>setDetailCode('')}><section className="event-dialog planner-detail-dialog" onMouseDown={event=>event.stopPropagation()}>{(()=>{const course=courseCatalog.find(item=>item.code===detailCode);return <><div className="audit-dialog-head"><div><span className="course-code">{detailCode}</span><h2>{course?.name||'Current enrolled course'}</h2><p>{course?.description||'This enrolled course is part of your current academic record.'}</p></div><button className="ghost square-button" onClick={()=>setDetailCode('')}>×</button></div>{course&&<><div className="detail-facts"><span><b>Credits</b>{course.credits}</span><span><b>Prerequisite</b>{course.prerequisite}</span><span><b>Requirement</b>{course.requirement}</span></div><div className="planner-detail-actions"><button className="ghost" onClick={()=>{setDetailCode('');openCatalog(course.subject)}}>Explore alternatives</button><button className="primary" onClick={()=>{setDetailCode('');openCatalog(course.code)}}>View in catalog</button></div></>}</>})()}</section></div>}
  </>
}

function ProfilePage({profile,onPhotoSave,go}:{profile:StudentProfile;onPhotoSave:(photo:string)=>void;go:(page:Page)=>void}) {
  const uploadPhoto=(file?:File)=>{if(!file)return;const reader=new FileReader();reader.onload=()=>onPhotoSave(String(reader.result));reader.readAsDataURL(file)}
  return <div className="account-page profile-page">
    <article className="card profile-hero-card"><div className="profile-photo">{profile.photo?<img src={profile.photo} alt={profile.name}/>:profile.name.split(' ').map(part=>part[0]).join('').slice(0,2)}</div><div><span className="eyebrow">STUDENT PROFILE</span><h2>{profile.name}</h2><p>{profile.degree} · {profile.major}</p><span className="profile-standing"><Icon name="check" size={14}/>{profile.standing}</span></div><div className="profile-hero-actions"><label className="ghost photo-upload">Update photo<input type="file" accept="image/*" onChange={event=>uploadPhoto(event.target.files?.[0])}/></label>{profile.photo&&<button className="ghost" onClick={()=>onPhotoSave('')}>Remove photo</button>}</div></article>
    <div className="official-info-note"><Icon name="settings" size={16}/><span>Academic and identity information is managed by Southern Arkansas University. Contact your university to request corrections.</span></div>
    <div className="account-grid">
      <article className="card account-section"><div className="account-section-head"><span className="feature-icon blue"><Icon name="user"/></span><div><h2>University-managed information</h2><p>Read-only information from the student information system.</p></div></div><div className="profile-fields"><label>Official name<strong>{profile.name}</strong><small>University-managed identity</small></label><label>Student email<strong>{profile.email}</strong><small>University-issued account</small></label><label>University<strong>{profile.university}</strong><small>Official institution record</small></label><label>Major / Minor<strong>{profile.major} · {profile.minor}</strong><small>Official academic record</small></label><label>Degree program<strong>{profile.degree}</strong><small>Official academic record</small></label><label>Expected graduation<strong>{profile.graduation}</strong><small>Projection based on official and planned coursework</small></label></div></article>
      <article className="card academic-summary-card"><div className="account-section-head"><span className="feature-icon green"><Icon name="chart"/></span><div><h2>Academic summary</h2><p>Your current official standing.</p></div></div><div className="profile-stat-row"><span><b>82</b> of 120 credits</span><span><b>68%</b> complete</span></div><div className="profile-academic-detail"><span>Academic standing<strong>{profile.standing}</strong></span><span>Expected graduation<strong>{profile.graduation}</strong></span></div><button className="text-btn" onClick={()=>go('Degree Progress')}>View degree progress <Icon name="arrow" size={14}/></button><button className="text-btn" onClick={()=>go('Semester Planner')}>Open semester roadmap <Icon name="arrow" size={14}/></button></article>
    </div>
  </div>
}

function SchedulingPreferencesPage({preferences,onSave,onNotify}:{preferences:SchedulingPreferences;onSave:(preferences:SchedulingPreferences)=>void;onNotify:(message:string)=>void}) {
  const defaults:SchedulingPreferences={time:'Midday',days:['Mon','Tue','Wed','Thu'],minCredits:12,maxCredits:16,delivery:['Face-to-face','Hybrid'],distance:'Under 15 minutes',minRating:4,flexibility:'Balanced'}
  const [draft,setDraft]=useState(preferences)
  const toggle=(key:'days'|'delivery',value:string)=>setDraft(current=>({...current,[key]:current[key].includes(value)?current[key].filter(item=>item!==value):[...current[key],value]}))
  const save=()=>{onSave(draft);onNotify('Scheduling preferences saved')}
  return <div className="account-page preferences-page">
    <article className="card preferences-intro"><span className="feature-icon purple"><Icon name="sliders"/></span><div><h2>Build schedules around your priorities</h2><p>Create Schedule and Flow use these preferences when comparing sections. Required courses and fixed commitments still take priority.</p></div><span className="pill">{draft.flexibility} flexibility</span></article>
    <div className="preference-grid">
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon teal"><Icon name="calendar"/></span><div><h2>Time and days</h2><p>When you prefer to attend class.</p></div></div><label>Preferred class time<select value={draft.time} onChange={event=>setDraft({...draft,time:event.target.value})}><option>Morning</option><option>Midday</option><option>Afternoon</option><option>Evening</option><option>No preference</option></select></label><span className="field-label">Preferred days</span><div className="choice-pills">{['Mon','Tue','Wed','Thu','Fri'].map(day=><button className={draft.days.includes(day)?'active':''} key={day} onClick={()=>toggle('days',day)}>{day}</button>)}</div></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon blue"><Icon name="book"/></span><div><h2>Course load</h2><p>Set a comfortable semester range.</p></div></div><div className="range-fields"><label>Minimum credits<input type="number" min="1" max={draft.maxCredits} value={draft.minCredits} onChange={event=>setDraft({...draft,minCredits:Number(event.target.value)})}/></label><label>Maximum credits<input type="number" min={draft.minCredits} max="24" value={draft.maxCredits} onChange={event=>setDraft({...draft,maxCredits:Number(event.target.value)})}/></label></div><label>Preference flexibility<select value={draft.flexibility} onChange={event=>setDraft({...draft,flexibility:event.target.value as SchedulingPreferences['flexibility']})}><option>Flexible</option><option>Balanced</option><option>Strict</option></select></label></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon orange"><Icon name="layers"/></span><div><h2>Format and location</h2><p>How and where classes meet.</p></div></div><span className="field-label">Delivery formats</span><div className="choice-pills wide-pills">{['Face-to-face','Hybrid','Online'].map(format=><button className={draft.delivery.includes(format)?'active':''} key={format} onClick={()=>toggle('delivery',format)}>{format}</button>)}</div><label>Maximum travel between classes<select value={draft.distance} onChange={event=>setDraft({...draft,distance:event.target.value})}><option>Under 10 minutes</option><option>Under 15 minutes</option><option>Under 25 minutes</option><option>No preference</option></select></label></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon pink"><Icon name="user"/></span><div><h2>Instructor preference</h2><p>Use ratings as a scheduling signal.</p></div></div><span className="field-label">Minimum professor rating</span><div className="rating-preference">{[1,2,3,4,5].map(value=><button className={draft.minRating>=value?'active':''} key={value} onClick={()=>setDraft({...draft,minRating:value})}>★</button>)}<strong>{draft.minRating}.0+</strong></div><small>Ratings never override prerequisites or required course sequencing.</small></article>
    </div>
    <div className="account-save-bar"><button className="ghost" onClick={()=>setDraft(defaults)}>Reset defaults</button><button className="primary" onClick={save}>Save preferences</button></div>
  </div>
}

function SettingsPage({settings,onSave,onNotify,profile,onAppearanceChange}:{settings:AppSettings;onSave:(settings:AppSettings)=>void;onNotify:(message:string)=>void;profile:StudentProfile;onAppearanceChange:(appearance:AppSettings['appearance'])=>void}) {
  const [draft,setDraft]=useState(settings)
  const toggle=(key:keyof AppSettings)=>setDraft(current=>({...current,[key]:!current[key]}))
  const sections=[{title:'Notifications',icon:'bell',tone:'orange',items:[['emailNotifications','Email notifications','Degree and scheduling updates by email'],['pushNotifications','Push notifications','Time-sensitive reminders in Flowsaic'],['advisorUpdates','Advisor updates','Approval status and advisor feedback'],['scheduleAlerts','Schedule alerts','Conflicts, seat changes, and deadlines']]},{title:'Accessibility',icon:'eye',tone:'teal',items:[['highContrast','Higher contrast','Increase borders and text contrast'],['largerText','Larger interface text','Increase core interface sizing'],['reduceMotion','Reduce motion','Minimize transitions and movement']]}] as const
  const save=()=>{onSave(draft);onNotify('Settings saved across Flowsaic')}
  return <div className="account-page settings-page">
    <div className="settings-grid">
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon blue"><Icon name="user"/></span><div><h2>Account</h2><p>Official identity and authentication.</p></div></div><div className="readonly-account-fields"><span><small>Official name</small><strong>{profile.name}</strong></span><span><small>Student email</small><strong>{profile.email}</strong></span><span><small>Institution</small><strong>{profile.university}</strong></span></div><p className="university-managed-caption">Identity information is read-only and managed by Southern Arkansas University.</p><label>Profile visibility<select value={draft.profileVisibility} onChange={event=>setDraft({...draft,profileVisibility:event.target.value as AppSettings['profileVisibility']})}><option>Private</option><option>Advisors only</option><option>University community</option></select></label><button className="ghost settings-action" onClick={()=>onNotify('Password change flow opened')}>Change password</button></article>
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon purple"><Icon name="settings"/></span><div><h2>Appearance</h2><p>Light is the default. System follows your device.</p></div></div><div className="appearance-options">{(['Light','Dark','System'] as const).map(option=><button className={draft.appearance===option?'active':''} aria-pressed={draft.appearance===option} key={option} onClick={()=>{setDraft({...draft,appearance:option});onAppearanceChange(option)}}><span className={`theme-preview ${option.toLowerCase()}`}/><strong>{option}</strong></button>)}</div></article>
      {sections.map(section=><article className="card settings-card settings-list-card" key={section.title}><div className="account-section-head"><span className={`feature-icon ${section.tone}`}><Icon name={section.icon}/></span><div><h2>{section.title}</h2><p>Choose what works best for you.</p></div></div>{section.items.map(([key,label,description])=><button className="setting-row" key={key} onClick={()=>toggle(key)}><span><strong>{label}</strong><small>{description}</small></span><i className={draft[key]?'active':''}/></button>)}</article>)}
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon green"><Icon name="settings"/></span><div><h2>Privacy</h2><p>How your academic context is used.</p></div></div><p className="settings-copy">Flow uses your degree audit, planned courses, and calendar commitments to provide guidance. Flowsaic does not mark planned courses as completed.</p><button className="ghost settings-action">Review data controls</button></article>
    </div>
    <div className="account-save-bar"><button className="ghost" onClick={()=>setDraft(settings)}>Discard changes</button><button className="primary" onClick={save}>Save settings</button></div>
  </div>
}

function HelpSupportPage({onNotify}:{onNotify:(message:string)=>void}) {
  const [query,setQuery]=useState('')
  const [open,setOpen]=useState('')
  const faqs=[['How does degree planning work?','Degree Progress separates officially completed credits from in-progress enrollment and future planned courses.'],['How does Create Schedule avoid conflicts?','It compares course sections with enrolled classes, fixed commitments, and your saved scheduling preferences.'],['What happens when prerequisites are not met?','Flowsaic flags the course and prevents invalid section scheduling until the prerequisite is completed or planned earlier.'],['How does Flow use my information?','Flow references your degree audit, semester roadmap, calendar commitments, preferences, and saved schedule to tailor guidance.'],['How does advisor approval work?','Submit a conflict-free schedule from Create Schedule. Your advisor can approve it or request revisions before registration.']]
  const shown=faqs.filter(item=>item.join(' ').toLowerCase().includes(query.toLowerCase()))
  return <div className="account-page help-page">
    <article className="help-hero card"><span className="feature-icon purple"><Icon name="help"/></span><div><h2>How can we help?</h2><p>Search Flowsaic guidance or contact the support team.</p></div><div className="help-search"><Icon name="search" size={18}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search degree planning, schedules, prerequisites…"/></div></article>
    <div className="help-layout"><article className="card faq-card"><div className="account-section-head"><span className="feature-icon blue"><Icon name="book"/></span><div><h2>Frequently asked questions</h2><p>{shown.length} helpful answers</p></div></div>{shown.map(([question,answer])=><section className="faq-item" key={question}><button onClick={()=>setOpen(open===question?'':question)}><strong>{question}</strong><Icon name="arrow" size={16}/></button>{open===question&&<p>{answer}</p>}</section>)}{!shown.length&&<div className="help-empty"><strong>No matching answers</strong><p>Try a broader phrase or contact support.</p></div>}</article><aside className="help-side"><article className="card support-card"><span className="feature-icon teal"><Icon name="mail"/></span><h2>Contact support</h2><p>Get help with your Flowsaic account or report an issue with the prototype. Academic record corrections are handled by Southern Arkansas University.</p><button className="primary" onClick={()=>onNotify('Support request started')}>Contact support</button><button className="ghost" onClick={()=>onNotify('Issue report form opened')}>Report an issue</button></article><article className="card flow-reminder"><img src="/assets/flow-koi.png" alt="Flow koi icon"/><div><strong>Flow provides AI guidance</strong><p>Confirm official degree requirements, registration decisions, and graduation eligibility with your Southern Arkansas University advisor.</p></div></article></aside></div>
  </div>
}

function CalendarPage({events,onAdd,onUpdate,onRemove,askFlow}:{events:CalendarEvent[];onAdd:(event:CalendarEvent)=>void;onUpdate:(event:CalendarEvent)=>void;onRemove:(id:string)=>void;askFlow:()=>void}) {
  const dayKeys: CalendarEvent['day'][]=['Mon','Tue','Wed','Thu','Fri']
  const categories:EventCategory[]=['Academic','Work','Personal / Study','Extracurricular']
  const categoryTone:Record<EventCategory,string>={Academic:'blue',Work:'orange','Personal / Study':'purple',Extracurricular:'mint'}
  const [view,setView]=useState<'day'|'week'|'month'>(()=>{const saved=localStorage.getItem('flowsaic-calendar-view');return saved==='day'||saved==='month'?saved:'week'})
  const [anchor,setAnchor]=useState(()=>{const saved=localStorage.getItem('flowsaic-calendar-date');return saved?new Date(saved):new Date(2025,9,13)})
  const [visibleCategories,setVisibleCategories]=useState<EventCategory[]>(categories)
  const [showProposed,setShowProposed]=useState(true)
  const [dialogOpen,setDialogOpen]=useState(false)
  const [editingId,setEditingId]=useState<string|null>(null)
  const [applyScope,setApplyScope]=useState<'occurrence'|'series'>('series')
  const [draft,setDraft]=useState({day:'Mon' as CalendarEvent['day'],title:'',start:'12:00',end:'13:00',meta:'',category:'Personal / Study' as EventCategory,recurrence:'Weekly' as CalendarEvent['recurrence'],priority:'Normal' as CalendarEvent['priority'],fixed:false})
  const toInputTime=(time:string)=>{
    const [clock,period]=time.split(' ')
    const [hourText,minute]=clock.split(':')
    let hour=Number(hourText)
    if(period==='PM'&&hour!==12) hour+=12
    if(period==='AM'&&hour===12) hour=0
    return `${String(hour).padStart(2,'0')}:${minute}`
  }
  const toDisplayTime=(time:string)=>{
    const [hourText,minute]=time.split(':')
    const hour=Number(hourText)
    return `${hour%12||12}:${minute} ${hour>=12?'PM':'AM'}`
  }
  const asHour=(time:string)=>{
    const input=toInputTime(time)
    const [hour,minute]=input.split(':').map(Number)
    return hour+minute/60
  }
  const hourToDisplay=(value:number)=>{const hour=Math.floor(value);const minute=Math.round((value-hour)*60);return toDisplayTime(`${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`)}
  const proposedEvents:CalendarEvent[]=(()=>{
    try {
      const scheduleDraft=JSON.parse(localStorage.getItem('flowsaic-schedule-draft')||'{}') as {selectedSections?:Record<string,string>}
      return Object.entries(scheduleDraft.selectedSections||{}).flatMap(([code,sectionId])=>{const course=courseCatalog.find(item=>item.code===code);const section=course?.sections.find(item=>item.id===sectionId);return section?.meetings.map((meeting,index)=>({id:`proposed-${code}-${sectionId}-${index}`,day:dayKeys[meeting.day],time:hourToDisplay(meeting.start),endTime:hourToDisplay(meeting.end),title:`Proposed · ${code}`,meta:`${course?.name} · Section ${sectionId}`,tone:'proposed',type:'Class' as const,category:'Academic' as const,recurrence:'None' as const,priority:'Normal' as const,fixed:true,readOnly:true}))||[]})
    } catch {
      return []
    }
  })()
  const selectedEvent=[...events,...proposedEvents].find(event=>event.id===editingId)
  const isReadOnly=Boolean(selectedEvent?.readOnly)
  useEffect(()=>{localStorage.setItem('flowsaic-calendar-view',view);localStorage.setItem('flowsaic-calendar-date',anchor.toISOString())},[view,anchor])
  const startOfWeek=(date:Date)=>{
    const start=new Date(date)
    const weekday=start.getDay()
    start.setDate(start.getDate()-(weekday===0?6:weekday-1))
    return start
  }
  const weekStart=startOfWeek(anchor)
  const dayDates=dayKeys.map((key,index)=>{const date=new Date(weekStart);date.setDate(date.getDate()+index);return {key,date}})
  const activeDay=(anchor.getDay()>=1&&anchor.getDay()<=5?dayKeys[anchor.getDay()-1]:'Mon')
  const shownDays=view==='day'?dayDates.filter(day=>day.key===activeDay):dayDates
  const visibleEvents=[...events.filter(event=>visibleCategories.includes(event.category)),...(showProposed?proposedEvents:[])]
  const dateRange=view==='month'
    ? anchor.toLocaleDateString('en-US',{month:'long',year:'numeric'})
    : view==='day'
      ? anchor.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'})
      : `${dayDates[0].date.toLocaleDateString('en-US',{month:'long',day:'numeric'})}–${dayDates[4].date.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}`
  const navigate=(direction:number)=>{
    const next=new Date(anchor)
    if(view==='day'){
      next.setDate(next.getDate()+direction)
      while(next.getDay()===0||next.getDay()===6) next.setDate(next.getDate()+direction)
    }
    else if(view==='week') next.setDate(next.getDate()+direction*7)
    else next.setMonth(next.getMonth()+direction)
    setAnchor(next)
  }
  const openNew=()=>{setEditingId(null);setApplyScope('series');setDraft({day:activeDay,title:'',start:'12:00',end:'13:00',meta:'',category:'Personal / Study',recurrence:'Weekly',priority:'Normal',fixed:false});setDialogOpen(true)}
  const openEvent=(event:CalendarEvent)=>{setEditingId(event.id);setApplyScope('series');setDraft({day:event.day,title:event.title,start:toInputTime(event.time),end:toInputTime(event.endTime),meta:event.meta,category:event.category,recurrence:event.recurrence,priority:event.priority,fixed:event.fixed});setDialogOpen(true)}
  const saveEvent=()=>{
    if(!draft.title.trim()||draft.end<=draft.start) return
    const event:CalendarEvent={id:editingId||`calendar-${Date.now()}`,day:draft.day,title:draft.title.trim(),time:toDisplayTime(draft.start),endTime:toDisplayTime(draft.end),meta:draft.meta.trim()||'No location added',tone:categoryTone[draft.category],type:'Personal commitment',category:draft.category,recurrence:editingId&&selectedEvent?.recurrence==='Weekly'&&applyScope==='occurrence'?'None':draft.recurrence,priority:draft.priority,fixed:draft.fixed,readOnly:false}
    editingId?onUpdate(event):onAdd(event)
    setDialogOpen(false)
  }
  const draftConflict=events.some(event=>event.id!==editingId&&event.day===draft.day&&asHour(event.time)<Number(draft.end.split(':')[0])+Number(draft.end.split(':')[1])/60&&Number(draft.start.split(':')[0])+Number(draft.start.split(':')[1])/60<asHour(event.endTime))
  const monthStart=new Date(anchor.getFullYear(),anchor.getMonth(),1)
  const monthGridStart=startOfWeek(monthStart)
  const monthDates=Array.from({length:42},(_,index)=>{const date=new Date(monthGridStart);date.setDate(date.getDate()+index);return date})
  const eventStyle=(event:CalendarEvent,dayEvents:CalendarEvent[])=>{
    const start=asHour(event.time)
    const end=asHour(event.endTime)
    const overlaps=dayEvents.filter(other=>other.id!==event.id&&start<asHour(other.endTime)&&asHour(other.time)<end)
    const lane=overlaps.some(other=>asHour(other.time)<=start)?1:0
    return {top:`${(start-8)*76+5}px`,height:`${Math.max((end-start)*76-9,34)}px`,left:overlaps.length?`${lane*50+3}%`:'3%',width:overlaps.length?'47%':'94%'}
  }
  return <div className="calendar-workspace">
    <article className="card calendar-card">
      <div className="calendar-toolbar">
        <div className="calendar-date-nav"><button className="ghost square-button" aria-label="Previous" onClick={()=>navigate(-1)}><span className="previous-arrow"><Icon name="arrow" size={16}/></span></button><button className="ghost" onClick={()=>setAnchor(new Date(2025,9,13))}>Today</button><button className="ghost square-button" aria-label="Next" onClick={()=>navigate(1)}><Icon name="arrow" size={16}/></button><div><h2>{dateRange}</h2><p>{visibleEvents.length} visible events · 8:00 AM–8:00 PM</p></div></div>
        <div className="calendar-toolbar-actions"><div className="view-tabs">{(['day','week','month'] as const).map(option=><button key={option} className={view===option?'active':''} onClick={()=>setView(option)}>{option[0].toUpperCase()+option.slice(1)}</button>)}</div><button className="ghost ask-calendar-button" onClick={askFlow}><Icon name="chat" size={16}/> Ask Flow</button><button className="primary" onClick={openNew}><Icon name="plus"/> Add event</button></div>
      </div>
      <div className="calendar-category-filters">{categories.map(category=><button key={category} className={visibleCategories.includes(category)?'active':''} onClick={()=>setVisibleCategories(current=>current.includes(category)?current.filter(item=>item!==category):[...current,category])}><i className={categoryTone[category]}/>{category}</button>)}{proposedEvents.length>0&&<button className={showProposed?'active proposed-filter':''} onClick={()=>setShowProposed(value=>!value)}><i className="proposed"/>Proposed schedule</button>}</div>
      {view==='month'
        ? <div className="calendar-month"><div className="calendar-month-weekdays">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day=><span key={day}>{day}</span>)}</div><div className="calendar-month-grid">{monthDates.map(date=>{const dayKey=dayKeys[date.getDay()-1];const dateEvents=dayKey?visibleEvents.filter(event=>event.day===dayKey):[];return <button disabled={!dayKey} key={date.toISOString()} className={`${date.getMonth()!==anchor.getMonth()?'outside':''} ${date.toDateString()===anchor.toDateString()?'selected':''}`} onClick={()=>{setAnchor(date);setView('day')}}><strong>{date.getDate()}</strong>{dateEvents.slice(0,3).map(event=><span className={event.tone} key={event.id}>{event.title}</span>)}{dateEvents.length>3&&<small>+{dateEvents.length-3} more</small>}</button>})}</div></div>
        : <div className="calendar-time-shell"><div className="calendar-grid-head"><span/><div className="calendar-day-heads" style={{gridTemplateColumns:`repeat(${shownDays.length},minmax(150px,1fr))`}}>{shownDays.map(day=><div key={day.key}><strong>{day.key}</strong><span>{day.date.getDate()}</span></div>)}</div></div><div className="calendar-grid-body"><div className="calendar-time-rail">{Array.from({length:12},(_,index)=>index+8).map(hour=><span key={hour}>{hour===12?'12 PM':hour<12?`${hour} AM`:`${hour-12} PM`}</span>)}</div><div className="calendar-day-tracks" style={{gridTemplateColumns:`repeat(${shownDays.length},minmax(150px,1fr))`}}>{shownDays.map(day=>{const dayEvents=visibleEvents.filter(event=>event.day===day.key);return <div className="calendar-day-track" key={day.key}>{dayEvents.map(event=><button key={event.id} className={`calendar-grid-event ${event.tone}`} style={eventStyle(event,dayEvents)} onClick={()=>openEvent(event)}><small>{event.tone==='proposed'?'Proposed':event.type==='Class'?'Enrolled':'Personal'} · {event.time}–{event.endTime}</small><strong>{event.title}</strong><span>{event.meta}</span></button>)}</div>})}</div></div></div>}
    </article>
    {dialogOpen&&<div className="modal-backdrop" onMouseDown={()=>setDialogOpen(false)}><form className="event-dialog calendar-event-dialog" onMouseDown={event=>event.stopPropagation()} onSubmit={event=>{event.preventDefault();saveEvent()}}><div className="event-dialog-head"><span className="eyebrow">{editingId?'EVENT DETAILS':'NEW COMMITMENT'}</span><h2>{editingId?isReadOnly?(selectedEvent?.tone==='proposed'?'Proposed section details':'Class details'):'Edit event':'Add to calendar'}</h2><p>{isReadOnly?(selectedEvent?.tone==='proposed'?'This proposed section comes from your saved schedule and is edited in Create Schedule.':'Academic classes are synced from your enrolled courses and are read-only.'):'Changes here also inform schedule generation and Flow’s advice.'}</p></div><label>Event name<input autoFocus required disabled={isReadOnly} value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})}/></label><div className="event-dialog-row"><label>Category<select disabled={isReadOnly} value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value as EventCategory})}>{categories.map(category=><option key={category}>{category}</option>)}</select></label><label>Day<select disabled={isReadOnly} value={draft.day} onChange={event=>setDraft({...draft,day:event.target.value as CalendarEvent['day']})}>{dayKeys.map(day=><option key={day}>{day}</option>)}</select></label></div><div className="event-dialog-row"><label>Starts<input disabled={isReadOnly} type="time" min="08:00" max="19:59" required value={draft.start} onChange={event=>setDraft({...draft,start:event.target.value})}/></label><label>Ends<input disabled={isReadOnly} type="time" required value={draft.end} min={draft.start} max="20:00" onChange={event=>setDraft({...draft,end:event.target.value})}/></label></div><label>Location or details<input disabled={isReadOnly} value={draft.meta} onChange={event=>setDraft({...draft,meta:event.target.value})}/></label><div className="event-dialog-row"><label>Repeats<select disabled={isReadOnly} value={draft.recurrence} onChange={event=>setDraft({...draft,recurrence:event.target.value as CalendarEvent['recurrence']})}><option>None</option><option>Weekly</option></select></label><label>Priority<select disabled={isReadOnly} value={draft.priority} onChange={event=>setDraft({...draft,priority:event.target.value as CalendarEvent['priority']})}><option>Low</option><option>Normal</option><option>High</option></select></label></div>{!isReadOnly&&<label className="calendar-checkbox"><input type="checkbox" checked={draft.fixed} onChange={event=>setDraft({...draft,fixed:event.target.checked})}/><span><strong>Fixed commitment</strong><small>Block schedule generation from placing courses here.</small></span></label>}{editingId&&!isReadOnly&&selectedEvent?.recurrence==='Weekly'&&<div className="recurrence-scope"><span>Apply changes to</span><div><button type="button" className={applyScope==='occurrence'?'active':''} onClick={()=>setApplyScope('occurrence')}>This occurrence</button><button type="button" className={applyScope==='series'?'active':''} onClick={()=>setApplyScope('series')}>Entire series</button></div><small>{applyScope==='occurrence'?'Only this visible occurrence will change.':'Updates apply to the recurring weekly commitment.'}</small></div>}{!isReadOnly&&draft.end<=draft.start&&<p className="calendar-form-warning">End time must be after start time.</p>}{!isReadOnly&&draftConflict&&<p className="calendar-form-warning">This overlaps another event. You can save it, but the schedule builder will flag the conflict.</p>}<div className="event-dialog-actions">{editingId&&!isReadOnly&&<button type="button" className="remove-event-button" onClick={()=>{onRemove(editingId);setDialogOpen(false)}}>{selectedEvent?.recurrence==='Weekly'?(applyScope==='occurrence'?'Delete occurrence':'Delete series'):'Remove event'}</button>}<button type="button" className="ghost" onClick={()=>setDialogOpen(false)}>{isReadOnly?'Close':'Cancel'}</button>{!isReadOnly&&<button className="primary" type="submit">{editingId?'Save changes':'Add event'}</button>}</div></form></div>}
  </div>
}

type BuilderCourse = CourseRecord
type BuilderCalendarItem = ScheduleMeeting & { key:string; type:'course'|'commitment'; title:string; subtitle:string; meta:string; tone:string; courseCode?:string; fixed?:boolean }

function CreateSchedule({saveDraft,submit,askAdvisor,openPreferences,calendarEvents,plannedTerms,preferences}:{saveDraft:()=>void;submit:()=>void;askAdvisor:()=>void;openPreferences:()=>void;calendarEvents:CalendarEvent[];plannedTerms:PlannedTerms;preferences:SchedulingPreferences}) {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
  const hours = Array.from({length:13},(_,index)=>index+8)
  const courses: BuilderCourse[] = courseCatalog
  const timeAsHour=(time:string)=>{
    const [clock,period]=time.split(' ')
    const [hourText,minuteText]=clock.split(':')
    let hour=Number(hourText)
    if(period==='PM'&&hour!==12) hour+=12
    if(period==='AM'&&hour===12) hour=0
    return hour+Number(minuteText)/60
  }
  const dayNumber:Record<CalendarEvent['day'],number>={Mon:0,Tue:1,Wed:2,Thu:3,Fri:4}
  const commitments: BuilderCalendarItem[] = calendarEvents.filter(event=>event.type==='Personal commitment').map(event=>({
    key:event.id,
    type:'commitment',
    title:event.title,
    subtitle:event.fixed?'Fixed commitment':'Flexible activity',
    meta:event.meta,
    tone:event.tone,
    fixed:event.fixed,
    day:dayNumber[event.day],
    start:timeAsHour(event.time),
    end:timeAsHour(event.endTime),
  }))
  const [savedDraft]=useState<{selectedSections:Record<string,string>;sectionChoices:Record<string,string>;showCommitments:boolean;term?:string}|null>(()=>{
    try {
      const draft=localStorage.getItem('flowsaic-schedule-draft')
      return draft?JSON.parse(draft):null
    } catch {
      return null
    }
  })
  const [query,setQuery]=useState('')
  const [subject,setSubject]=useState('All subjects')
  const [timeFilter,setTimeFilter]=useState('Any time')
  const [showCommitments,setShowCommitments]=useState(savedDraft?.showCommitments??true)
  const activeTerm=savedDraft?.term||'Spring 2026'
  const [creditWarningDismissed,setCreditWarningDismissed]=useState(false)
  const [sidePanelOpen,setSidePanelOpen]=useState(true)
  const [flowPanelOpen,setFlowPanelOpen]=useState(true)
  const [catalogPanelOpen,setCatalogPanelOpen]=useState(true)
  const [reviewingConflicts,setReviewingConflicts]=useState(false)
  const [sectionChoices,setSectionChoices]=useState<Record<string,string>>(()=>({...Object.fromEntries(courses.map(course=>[course.code,course.sections[0].id])),...savedDraft?.sectionChoices}))
  const [selectedSections,setSelectedSections]=useState<Record<string,string>>(savedDraft?.selectedSections??{})
  const activeTermIndex=Object.keys(plannedTerms).indexOf(activeTerm)
  const prerequisitePlannedEarlier=(course:BuilderCourse)=>activeTermIndex>0&&Object.keys(plannedTerms).slice(0,activeTermIndex).some(term=>plannedTerms[term].includes(course.prerequisite))
  const isCourseEligible=(course:BuilderCourse)=>course.prerequisiteStatus==='Not Required'||course.prerequisiteStatus==='Completed'||prerequisitePlannedEarlier(course)||(course.prerequisiteStatus==='In Progress'&&course.concurrentAllowed)
  const eligibilityLabel=(course:BuilderCourse)=>{
    if(course.prerequisiteStatus==='Not Required') return 'Eligible · No prerequisite'
    if(course.prerequisiteStatus==='Completed') return 'Eligible · Prerequisite completed'
    if(prerequisitePlannedEarlier(course)) return `Eligible · ${course.prerequisite} planned earlier`
    return course.concurrentAllowed?'Eligible · Concurrent enrollment permitted':'Not eligible · Prerequisite in progress'
  }
  const selectedCourses: {course:BuilderCourse;section:CourseSection}[] = courses.flatMap(course=>{
    const section=course.sections.find(item=>item.id===selectedSections[course.code])
    return section?[{course,section}]:[]
  })
  const filteredCourses=courses.filter(course=>{
    const matchesQuery=`${course.code} ${course.name} ${course.subject}`.toLowerCase().includes(query.toLowerCase())
    const matchesSubject=subject==='All subjects'||course.subject===subject
    const selectedSection=course.sections.find(section=>section.id===sectionChoices[course.code])||course.sections[0]
    const starts=selectedSection.meetings[0].start
    const matchesTime=timeFilter==='Any time'||(timeFilter==='Morning'&&starts<12)||(timeFilter==='Afternoon'&&starts>=12)
    return matchesQuery&&matchesSubject&&matchesTime
  })
  const toggleCourse=(course:BuilderCourse)=>setSelectedSections(current=>{
    if(current[course.code]) {
      const next={...current}
      delete next[course.code]
      return next
    }
    if(!isCourseEligible(course)) return current
    return {...current,[course.code]:sectionChoices[course.code]||course.sections[0].id}
  })
  const chooseSection=(course:BuilderCourse,sectionId:string)=>{
    setSectionChoices(current=>({...current,[course.code]:sectionId}))
    if(selectedSections[course.code]) setSelectedSections(current=>({...current,[course.code]:sectionId}))
  }
  const formatHour=(hour:number)=>hour===12?'12 PM':hour<12?`${hour} AM`:`${hour-12} PM`
  const totalCredits=selectedCourses.reduce((total,item)=>total+item.course.credits,0)
  const eligibilityIssues=selectedCourses.filter(item=>!isCourseEligible(item.course))
  const overlaps=(first:ScheduleMeeting,second:ScheduleMeeting)=>first.day===second.day&&first.start<second.end&&second.start<first.end
  const courseEvents: BuilderCalendarItem[] = selectedCourses.flatMap(({course,section})=>section.meetings.map((meeting,index)=>({key:`${course.code}-${section.id}-${index}`,type:'course' as const,title:course.code,subtitle:course.name,meta:`Section ${section.id} · ${section.room}`,tone:course.tone,courseCode:course.code,...meeting})))
  const detectionItems=[...courseEvents,...commitments]
  const conflictPairs: [BuilderCalendarItem,BuilderCalendarItem][] = []
  const conflictKeys=new Set<string>()
  detectionItems.forEach((item,index)=>detectionItems.slice(index+1).forEach(other=>{
    if(overlaps(item,other)){
      conflictPairs.push([item,other])
      conflictKeys.add(item.key)
      conflictKeys.add(other.key)
    }
  }))
  const conflictCourseCodes=new Set(courseEvents.filter(item=>conflictKeys.has(item.key)).map(item=>item.courseCode).filter(Boolean) as string[])
  const suggestions=Array.from(conflictCourseCodes).flatMap(code=>{
    const selected=selectedCourses.find(item=>item.course.code===code)
    if(!selected) return []
    const otherItems=[...courseEvents.filter(item=>item.courseCode!==code),...commitments.filter(item=>item.fixed)]
    const alternative=selected.course.sections.find(section=>section.id!==selected.section.id&&section.meetings.every(meeting=>otherItems.every(item=>!overlaps(meeting,item))))
    return alternative?[{course:selected.course,section:alternative}]:[]
  })
  const applySuggestion=(course:BuilderCourse,section:CourseSection)=>{
    setSectionChoices(current=>({...current,[course.code]:section.id}))
    setSelectedSections(current=>({...current,[course.code]:section.id}))
  }
  const preferenceScore=(course:BuilderCourse,section:CourseSection)=>{
    const averageStart=section.meetings.reduce((total,meeting)=>total+meeting.start,0)/section.meetings.length
    const timeMatch=preferences.time==='No preference'||(preferences.time==='Morning'&&averageStart<12)||(preferences.time==='Midday'&&averageStart>=10&&averageStart<15)||(preferences.time==='Afternoon'&&averageStart>=12&&averageStart<17)||(preferences.time==='Evening'&&averageStart>=16)
    const dayKeys=['Mon','Tue','Wed','Thu','Fri']
    const dayMatch=section.meetings.every(meeting=>preferences.days.includes(dayKeys[meeting.day]))
    return (preferences.delivery.includes(course.delivery)?3:0)+(timeMatch?2:0)+(dayMatch?2:0)+(section.rating>=preferences.minRating?2:0)
  }
  const autoGenerate=()=>{
    const generated:Record<string,string>={}
    const scheduled:ScheduleMeeting[]=[]
    const fixedCommitments=commitments.filter(item=>item.fixed)
    ;(plannedTerms[activeTerm]||['CS 410','CS 365','MATH 310','ENG 330']).forEach(code=>{
      const course=courses.find(item=>item.code===code)
      if(!course||!isCourseEligible(course)) return
      const section=[...course.sections].sort((first,second)=>preferenceScore(course,second)-preferenceScore(course,first)).find(option=>option.meetings.every(meeting=>[...scheduled,...fixedCommitments].every(item=>!overlaps(meeting,item))))
      if(section){
        generated[course.code]=section.id
        scheduled.push(...section.meetings)
      }
    })
    setSectionChoices(current=>({...current,...generated}))
    setSelectedSections(generated)
  }
  const visibleCalendarItems=showCommitments?[...courseEvents,...commitments]:courseEvents
  const calendarItemStyle=(item:BuilderCalendarItem)=>{
    const overlapping=visibleCalendarItems.filter(other=>overlaps(item,other)).sort((first,second)=>first.key.localeCompare(second.key))
    const lane=Math.max(0,overlapping.findIndex(other=>other.key===item.key))
    const count=overlapping.length
    return {
      gridColumn:item.day+2,
      gridRow:`${Math.floor(item.start)-6} / span ${Math.max(1,Math.ceil(item.end-item.start))}`,
      ...(count>1?{width:`calc(${100/count}% - 6px)`,marginLeft:`calc(${lane*100/count}% + 3px)`,marginRight:0}:{}),
    }
  }
  const persistSchedule=()=>localStorage.setItem('flowsaic-schedule-draft',JSON.stringify({selectedSections,sectionChoices,showCommitments,term:activeTerm}))
  const persistDraft=()=>{
    persistSchedule()
    saveDraft()
  }
  const submitForApproval=()=>{
    persistSchedule()
    submit()
  }

  return <div className={`schedule-builder ${sidePanelOpen?'':'side-collapsed'} ${reviewingConflicts?'reviewing-conflicts':''}`}>
    <article className="card timetable-card">
      <div className="builder-head"><div><span className="eyebrow">{activeTerm.toUpperCase()}</span><h2 className="weekly-schedule-title">Weekly schedule</h2><p>{preferences.flexibility} preferences · {preferences.time.toLowerCase()} classes · {preferences.minCredits}–{preferences.maxCredits} credits</p></div><div className="builder-head-actions"><button className="ghost" onClick={openPreferences}><Icon name="sliders" size={15}/> Preferences</button><button className="ghost panel-toggle" onClick={()=>setSidePanelOpen(value=>!value)}><Icon name="layers" size={15}/>{sidePanelOpen?'Hide panels':'Show panels'}</button><button className="ghost" disabled={!selectedCourses.length} onClick={()=>setSelectedSections({})}>Clear</button><button className="primary" onClick={autoGenerate}><Icon name="spark" size={16}/> Auto-generate</button></div></div>
      <div className="builder-summary"><div><span>Courses</span><strong>{selectedCourses.length}</strong></div><div className="credit-stat"><span>Credit hours</span><strong>{totalCredits}</strong>{totalCredits>18&&!creditWarningDismissed&&<div className="compact-credit-advisory"><Icon name="book" size={15}/><span><strong>High load:</strong> {totalCredits} credits exceeds the recommended 18.</span><button aria-label="Dismiss high credit load warning" onClick={()=>setCreditWarningDismissed(true)}>×</button></div>}</div><div className={conflictPairs.length?'has-conflicts':''}><span>Conflicts</span><strong>{conflictPairs.length}</strong></div><div className="commitment-controls"><button className={`commitment-toggle ${showCommitments?'active':''}`} aria-pressed={showCommitments} onClick={()=>setShowCommitments(value=>!value)}><i/><span>{showCommitments?'Hide':'Show'} commitments</span></button><small><b className="fixed-key"/> Fixed <b className="flexible-key"/> Flexible</small></div></div>
      {conflictPairs.length>0&&<div className="builder-alerts"><div className="schedule-warning conflict-warning"><Icon name="calendar" size={18}/><div><strong>{conflictPairs.length} schedule {conflictPairs.length===1?'conflict':'conflicts'} detected</strong><span>Select review to focus the affected events, or apply a compatible section.</span><span className="conflict-actions"><button onClick={()=>setReviewingConflicts(value=>!value)}>{reviewingConflicts?'Show all events':'Review on timetable'}</button>{suggestions.map(({course,section})=><button key={`${course.code}-${section.id}`} onClick={()=>{applySuggestion(course,section);setReviewingConflicts(false)}}>Try {course.code} section {section.id}</button>)}</span></div></div></div>}
      <div className="timetable-scroll">
        <div className="builder-timetable">
          <div className="timetable-corner">TIME</div>
          {days.map(day=><div className="timetable-day" key={day}>{day}</div>)}
          {hours.map((hour,hourIndex)=><div className="timetable-hour-row" key={hour}><div className="timetable-time" style={{gridColumn:1,gridRow:hourIndex+2}}>{formatHour(hour)}</div>{days.map((day,dayIndex)=><div className="timetable-cell" style={{gridColumn:dayIndex+2,gridRow:hourIndex+2}} key={`${day}-${hour}`}/>)}</div>)}
          {visibleCalendarItems.map(item=>item.type==='course'?<button className={`builder-course-event ${item.tone} ${conflictKeys.has(item.key)?'event-conflict':''} ${reviewingConflicts&&conflictKeys.has(item.key)?'conflict-focused':''}`} style={calendarItemStyle(item)} key={item.key} onClick={()=>{const course=courses.find(course=>course.code===item.courseCode);if(course)toggleCourse(course)}} title={`Remove ${item.title}`}><strong>{item.title}</strong><span>{item.subtitle}</span><small>{item.meta}</small>{conflictKeys.has(item.key)&&<em>Conflict</em>}</button>:<div className={`builder-course-event commitment-event ${item.tone} ${conflictKeys.has(item.key)?'event-conflict':''} ${reviewingConflicts&&conflictKeys.has(item.key)?'conflict-focused':''}`} style={calendarItemStyle(item)} key={item.key}><strong>{item.title}</strong><span>{item.subtitle}</span><small>{item.meta}</small>{conflictKeys.has(item.key)&&<em>Conflict</em>}</div>)}
        </div>
      </div>
      <div className="builder-footer"><span className={conflictPairs.length||eligibilityIssues.length?'conflict-status':''}><i className="status-dot"/> {conflictPairs.length?`${conflictPairs.length} conflicts need attention`:eligibilityIssues.length?'Resolve eligibility issues before submitting':'No schedule conflicts'}</span><div className="builder-submit-actions"><button className="ghost" onClick={persistDraft}>Save draft</button><button className="primary" disabled={!selectedCourses.length||conflictPairs.length>0||eligibilityIssues.length>0} title={conflictPairs.length?'Resolve conflicts before submitting':eligibilityIssues.length?'Resolve eligibility issues before submitting':''} onClick={submitForApproval}>Submit for approval</button></div></div>
    </article>
    {sidePanelOpen&&<div className="builder-side">
      <article className={`ai-card builder-ai-insight ${flowPanelOpen?'':'panel-collapsed'}`}><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon"/><div><span className="eyebrow">AI INSIGHT</span><h3>Need schedule help?</h3>{flowPanelOpen&&<><p>Balance sections and resolve conflicts.</p><button onClick={askAdvisor}><Icon name="chat" size={15}/> Consult AI Advisor</button></>}</div><button className="insight-collapse" aria-label={flowPanelOpen?'Collapse Flow assistance':'Expand Flow assistance'} onClick={()=>setFlowPanelOpen(value=>!value)}>{flowPanelOpen?'−':'+'}</button></article>
      <aside className="card builder-catalog">
        <div className="catalog-panel-head"><div><span className="eyebrow">COURSE CATALOG</span><h2>Find courses</h2></div><span className="panel-head-actions"><span className="pill">{filteredCourses.length} results</span><button className="panel-collapse-button" aria-label={catalogPanelOpen?'Collapse course catalog':'Expand course catalog'} onClick={()=>setCatalogPanelOpen(value=>!value)}>{catalogPanelOpen?'−':'+'}</button></span></div>
        {catalogPanelOpen&&<><div className="builder-search"><Icon name="search" size={17}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search courses…"/></div>
        <div className="builder-filters"><select value={subject} onChange={event=>setSubject(event.target.value)}><option>All subjects</option><option>Computer Science</option><option>Design</option><option>Mathematics</option><option>Economics</option><option>English</option><option>Psychology</option></select><select value={timeFilter} onChange={event=>setTimeFilter(event.target.value)}><option>Any time</option><option>Morning</option><option>Afternoon</option></select></div>
        <div className="builder-course-list">{filteredCourses.map(course=>{const eligible=isCourseEligible(course);const added=Boolean(selectedSections[course.code]);const selectedSection=course.sections.find(section=>section.id===sectionChoices[course.code])||course.sections[0];return <article className={`builder-course ${added?'added':''} ${!eligible?'ineligible-course':''}`} key={course.code}><div className="builder-course-top"><span className="course-code">{course.code}</span><span className={`eligibility ${eligible?'eligible':'ineligible'}`}>{eligibilityLabel(course)}</span></div><h3>{course.name}</h3><div className="section-picker"><label>Available section<select value={selectedSection.id} onChange={event=>chooseSection(course,event.target.value)}>{course.sections.map(section=><option value={section.id} key={section.id}>Section {section.id} · {section.schedule}</option>)}</select></label></div><div className="course-section-details"><p><strong>{selectedSection.schedule}</strong></p><p>{selectedSection.instructor} · {selectedSection.room}</p><p>Prerequisite: {course.prerequisite} · {course.prerequisiteStatus}{course.prerequisiteStatus==='In Progress'&&course.concurrentAllowed?' · Concurrent enrollment allowed':''}</p></div><div className="course-card-foot"><span>{course.credits} credits</span><button disabled={!eligible} className={added?'remove-course':'add-catalog-course'} onClick={()=>toggleCourse(course)}>{added?<><Icon name="check" size={15}/> Added — remove</>:<><Icon name="plus" size={15}/> Add to schedule</>}</button></div></article>})}</div>
        {!filteredCourses.length&&<div className="catalog-empty"><Icon name="search"/><strong>No courses found</strong><span>Try changing your search or filters.</span></div>}</>}
      </aside>
    </div>}
  </div>
}

type AdvisorTopic = 'degree'|'requirements'|'semester'|'courses'|'schedule'
type AdvisorMessage = { role:'user'|'ai'; text:string; schedule?:boolean; topic?:AdvisorTopic }

function AIAdvisor({messages,onMessagesChange,started,onStartedChange,openSchedule,plannedTerms,calendarEvents,preferences,studentName}:{messages:AdvisorMessage[];onMessagesChange:(messages:AdvisorMessage[])=>void;started:boolean;onStartedChange:(started:boolean)=>void;openSchedule:()=>void;plannedTerms:PlannedTerms;calendarEvents:CalendarEvent[];preferences:SchedulingPreferences;studentName:string}) {
  const welcome=`Hi ${studentName.split(' ')[0]}! I'm Flow. I can help you explore courses, review your degree progress, and build a schedule around your commitments. What would you like to work on today?`
  const [text,setText]=useState('')
  const messagesRef=useRef<HTMLDivElement>(null)
  const futurePlan=Object.entries(plannedTerms).filter(([term])=>term!==completedTermName&&term!==currentTermName)
  const plannedCodes=futurePlan.flatMap(([,courses])=>courses)
  const plannedCredits=plannedCodes.reduce((total,code)=>total+(courseCatalog.find(course=>course.code===code)?.credits||3),0)
  const projectedTerm=futurePlan.filter(([,courses])=>courses.length).at(-1)?.[0]||'not yet projected'
  const fixedCommitments=calendarEvents.filter(event=>event.type==='Personal commitment'&&event.fixed)
  const [scheduleContext]=useState<{term?:string;selectedSections?:Record<string,string>}>(()=>{
    try {
      return JSON.parse(localStorage.getItem('flowsaic-schedule-draft')||'{}')
    } catch {
      return {}
    }
  })
  const activeScheduleTerm=scheduleContext.term||'Spring 2026'
  const selectedScheduleCount=Object.keys(scheduleContext.selectedSections||{}).length
  const selectedScheduleMeetings=Object.entries(scheduleContext.selectedSections||{}).flatMap(([code,sectionId])=>{const course=courseCatalog.find(item=>item.code===code);return course?.sections.find(section=>section.id===sectionId)?.meetings||[]})
  const calendarMeeting=(event:CalendarEvent):ScheduleMeeting=>{const [clock,period]=event.time.split(' ');const [endClock,endPeriod]=event.endTime.split(' ');const toNumber=(value:string,marker:string)=>{const [hour,minute]=value.split(':').map(Number);return hour%12+(marker==='PM'?12:0)+minute/60};return {day:{Mon:0,Tue:1,Wed:2,Thu:3,Fri:4}[event.day],start:toNumber(clock,period),end:toNumber(endClock,endPeriod)}}
  const scheduleConflictCount=selectedScheduleMeetings.filter(meeting=>calendarEvents.filter(event=>event.type==='Class'||event.fixed).some(event=>{const calendar=calendarMeeting(event);return meeting.day===calendar.day&&meeting.start<calendar.end&&calendar.start<meeting.end})).length
  const responses={
    degree:`You have 82 confirmed credits and ${plannedCredits} planned credits through ${projectedTerm}. The roadmap is an estimate until courses are completed, but its current sequence supports your projected graduation. Your strongest next step is to finish the remaining Computer Science core while continuing your Design minor.`,
    requirements:'Your remaining plan includes two Computer Science core courses, one mathematics requirement, three Design minor courses, and approved electives. CS 410 is available because CS 301 is complete. CS 430 still requires completed CS 365, so it should stay in a later semester rather than your Spring 2026 schedule.',
    semester:`Your current roadmap includes ${plannedCodes.join(', ')||'no future courses yet'}. I can rebalance these across terms, validate prerequisites, and target your preferred ${preferences.minCredits}–${preferences.maxCredits} credit range.`,
    courses:'CS 410 is a strong next course because you’ve completed CS 301 and it advances both your computing and design goals. CS 365 and MATH 310 also move key degree requirements forward. I can compare sections, instructors, and meeting times for any of them.',
    schedule:`Your latest ${activeScheduleTerm} schedule has ${selectedScheduleCount} selected ${selectedScheduleCount===1?'course':'courses'} and ${scheduleConflictCount} flagged ${scheduleConflictCount===1?'overlap':'overlaps'}. I’ll prioritize ${preferences.time.toLowerCase()} classes, ${preferences.delivery.join(' or ').toLowerCase()} delivery, and ${preferences.minRating}.0+ rated instructors around ${fixedCommitments.length} fixed commitments.`,
  }
  const continuedResponses={
    degree:`Building on your degree review, the official number remains 82 completed credits. Your ${plannedCredits}-credit roadmap through ${projectedTerm} is separate from that confirmed record and will update as you move courses.`,
    requirements:'Looking one level deeper, CS 365 should come before CS 430, while CS 410 can be taken now because CS 301 is complete. That prerequisite order keeps the plan valid without delaying your December 2026 projection.',
    semester:'Keeping the requirements we already reviewed in mind, Spring 2026 should stay near 13–15 credits. The four-course option balances core progress with your Design minor and leaves room for your fixed work commitments.',
    courses:'Based on the courses already discussed, the most useful comparison is between section timing and instructor fit. I can keep CS 410 in the plan and compare alternate sections for CS 365, MATH 310, or ENG 330.',
    schedule:`I’m keeping the latest ${activeScheduleTerm} selections, ${scheduleConflictCount} flagged overlaps, and ${fixedCommitments.length} fixed commitments in context. I can adjust section timing, workload, or preferred days without changing your degree roadmap.`,
  }
  const followUps:Record<AdvisorTopic,{label:string;topic:AdvisorTopic}[]> = {
    degree:[{label:'Review Requirements',topic:'requirements'},{label:'Plan Next Semester',topic:'semester'},{label:'Explore Courses',topic:'courses'}],
    requirements:[{label:'Plan Next Semester',topic:'semester'},{label:'Review Degree Progress',topic:'degree'},{label:'Explore Courses',topic:'courses'}],
    semester:[{label:'Build My Schedule',topic:'schedule'},{label:'Compare Course Options',topic:'courses'},{label:'Review Requirements',topic:'requirements'}],
    courses:[{label:'Plan Next Semester',topic:'semester'},{label:'Build My Schedule',topic:'schedule'},{label:'Review Requirements',topic:'requirements'}],
    schedule:[{label:'Review Course Options',topic:'courses'},{label:'Plan a Lighter Semester',topic:'semester'},{label:'Check Degree Progress',topic:'degree'}],
  }
  const responseFor=(topic:AdvisorTopic)=>messages.some(message=>message.role==='ai'&&message.topic===topic)?continuedResponses[topic]:responses[topic]
  const addExchange=(prompt:string,response:string,topic:AdvisorTopic,schedule=false)=>{
    onStartedChange(true)
    onMessagesChange([...messages,{role:'user',text:prompt},{role:'ai',text:response,schedule,topic}])
  }
  const runAction=(action:'degree'|'semester'|'schedule'|'courses')=>{
    const labels={degree:'Review My Degree',semester:'Plan Next Semester',schedule:'Build My Schedule',courses:'Explore Courses'}
    addExchange(labels[action],responseFor(action),action,action==='schedule')
  }
  const continueConversation=(label:string,topic:AdvisorTopic)=>addExchange(label,responseFor(topic),topic,topic==='schedule')
  const send=()=>{
    if(!text.trim()) return
    const prompt=text.trim()
    const normalized=prompt.toLowerCase()
    const kind:AdvisorTopic=normalized.includes('schedule')?'schedule':normalized.includes('requirement')?'requirements':normalized.includes('degree')||normalized.includes('graduate')?'degree':normalized.includes('course')?'courses':'semester'
    addExchange(prompt,responseFor(kind),kind,kind==='schedule')
    setText('')
  }
  const reviewSchedule=()=>onMessagesChange([...messages,{role:'user',text:'Review this schedule in more detail.'},{role:'ai',text:`I reviewed the ${selectedScheduleCount} selected ${activeScheduleTerm} courses against enrolled classes and ${fixedCommitments.length} fixed personal commitments. I’ll keep planned courses separate from completed records and flag any section-level overlap before submission.`,topic:'schedule'}])
  const newConversation=()=>{onMessagesChange([]);onStartedChange(false);setText('')}
  useEffect(()=>{
    if(!started||!messagesRef.current) return
    const frame=requestAnimationFrame(()=>messagesRef.current?.scrollTo({top:messagesRef.current.scrollHeight,behavior:'smooth'}))
    return()=>cancelAnimationFrame(frame)
  },[messages,started])
  return <section className={`advisor-chat flow-chat ${started?'conversation-active':''}`}><div className="chat-title"><img className="flow-avatar" src="/assets/flow-koi.png" alt="Flow koi icon"/><div><h2>Flow</h2><p>Your AI Academic Advisor</p>{!started&&<small className="flow-data-note"><i/> Uses your degree audit, course catalog, and calendar</small>}</div>{started&&<button className="new-conversation-button" onClick={newConversation}><Icon name="plus" size={15}/> New Conversation</button>}</div><div className="messages" ref={messagesRef}>{!started?<div className="flow-welcome-screen"><div className="message ai flow-welcome">{welcome}</div><div className="flow-suggestions"><button onClick={()=>runAction('degree')}><span className="soft-icon blue"><Icon name="chart"/></span><strong>Review My Degree</strong><small style={{fontSize:15}}>Check progress and requirements</small></button><button onClick={()=>runAction('semester')}><span className="soft-icon purple"><Icon name="layers"/></span><strong>Plan Next Semester</strong><small style={{fontSize:15}}>Choose courses that move you forward</small></button><button onClick={()=>runAction('schedule')}><span className="soft-icon orange"><Icon name="calendar"/></span><strong>Build My Schedule</strong><small style={{fontSize:15}}>Fit classes around commitments</small></button><button onClick={()=>runAction('courses')}><span className="soft-icon mint"><Icon name="book"/></span><strong>Explore Courses</strong><small style={{fontSize:15}}>Compare options and sections</small></button></div></div>:messages.map((message,index)=><div className={`flow-message-row ${message.role}`} key={index}><div className={`message ${message.role}`}>{message.text}{message.schedule&&<div className="flow-schedule-preview"><div className="flow-preview-head"><div><span className="eyebrow">SCHEDULE OPTION</span><strong>Balanced Spring 2026</strong></div><span className="pill success"><Icon name="check" size={13}/> Validated</span></div><div className="flow-preview-courses"><span><b>CS 410</b> Mon/Wed · 10:00 AM</span><span><b>CS 365</b> Mon/Wed · 8:00 AM</span><span><b>MATH 310</b> Tue/Thu · 9:00 AM</span><span><b>ENG 330</b> Tue/Thu · 4:00 PM</span></div><p><Icon name="check" size={14}/> Sections available · Prerequisites complete · No commitment conflicts</p><div className="flow-preview-actions"><button onClick={reviewSchedule}>Review</button><button onClick={()=>setText('Can you modify this schedule to keep Fridays free?')}>Modify</button><button className="primary" onClick={openSchedule}>Open in Create Schedule</button></div></div>}{message.role==='ai'&&message.topic&&index===messages.length-1&&<div className="flow-follow-ups">{followUps[message.topic].map(item=><button key={item.label} onClick={()=>continueConversation(item.label,item.topic)}>{item.label}</button>)}</div>}</div></div>)}</div><div className="flow-chat-footer"><div className="composer"><input value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Ask Flow about your academic plan..."/><button onClick={send}>Send</button></div><p className="flow-disclaimer">Flow is an AI assistant. Confirm important academic decisions and graduation requirements with your Southern Arkansas University advisor.</p></div></section>
}

function App() {
  const [page,setPage]=useState<Page>('Dashboard')
  const [sidebarOpen,setSidebarOpen]=useState(false)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const [toast,setToast]=useState('')
  const [calendarEvents,setCalendarEvents]=useState<CalendarEvent[]>(initialCalendarEvents)
  const [scheduleStatus,setScheduleStatus]=useState<ScheduleStatus>(()=>{
    const saved=localStorage.getItem('flowsaic-schedule-status')
    return saved==='Pending Approval'||saved==='Approved'||saved==='Draft Saved'?saved:'Draft Saved'
  })
  const [catalogFocus,setCatalogFocus]=useState('')
  const [flowMessages,setFlowMessages]=useState<AdvisorMessage[]>([])
  const [flowStarted,setFlowStarted]=useState(false)
  const [plannedTerms,setPlannedTerms]=useState<PlannedTerms>(()=>{
    try {
      const saved=localStorage.getItem('flowsaic-planned-terms')
      return saved?{[completedTermName]:initialPlannedTerms[completedTermName],...JSON.parse(saved)}:initialPlannedTerms
    } catch {
      return initialPlannedTerms
    }
  })
  const [profile,setProfile]=useState<StudentProfile>(()=>{
    try {
      const saved=JSON.parse(localStorage.getItem('flowsaic-profile')||'null') as StudentProfile|null
      return {...officialStudentProfile,photo:saved?.photo||''}
    } catch {
      return {...officialStudentProfile,photo:''}
    }
  })
  const [preferences,setPreferences]=useState<SchedulingPreferences>(()=>{
    const fallback={time:'Midday',days:['Mon','Tue','Wed','Thu'],minCredits:12,maxCredits:16,delivery:['Face-to-face','Hybrid'],distance:'Under 15 minutes',minRating:4,flexibility:'Balanced' as const}
    try{return JSON.parse(localStorage.getItem('flowsaic-preferences')||'null')||fallback}catch{return fallback}
  })
  const [settings,setSettings]=useState<AppSettings>(()=>{
    const fallback={emailNotifications:true,pushNotifications:true,advisorUpdates:true,scheduleAlerts:true,appearance:'Light' as const,highContrast:false,largerText:false,reduceMotion:false,profileVisibility:'Advisors only' as const}
    try{return JSON.parse(localStorage.getItem('flowsaic-settings')||'null')||fallback}catch{return fallback}
  })
  const [accountMenu,setAccountMenu]=useState<'sidebar'|'header'|null>(null)
  const [accountReturnPage,setAccountReturnPage]=useState<Page>('Dashboard')
  const [signOutConfirm,setSignOutConfirm]=useState(false)
  const [signedOut,setSignedOut]=useState(false)
  const accountMenuRef=useRef<HTMLDivElement>(null)
  const sidebarProfileRef=useRef<HTMLButtonElement>(null)
  const headerProfileRef=useRef<HTMLButtonElement>(null)
  useEffect(()=>localStorage.setItem('flowsaic-planned-terms',JSON.stringify(plannedTerms)),[plannedTerms])
  useEffect(()=>localStorage.setItem('flowsaic-profile',JSON.stringify(profile)),[profile])
  useEffect(()=>localStorage.setItem('flowsaic-preferences',JSON.stringify(preferences)),[preferences])
  useEffect(()=>localStorage.setItem('flowsaic-settings',JSON.stringify(settings)),[settings])
  useEffect(()=>{
    document.documentElement.dataset.appearance=settings.appearance.toLowerCase()
    const systemTheme=window.matchMedia('(prefers-color-scheme: dark)')
    const applyTheme=()=>{document.documentElement.dataset.theme=settings.appearance==='System'?(systemTheme.matches?'dark':'light'):settings.appearance.toLowerCase()}
    applyTheme()
    systemTheme.addEventListener('change',applyTheme)
    document.documentElement.classList.toggle('larger-text',settings.largerText)
    document.documentElement.classList.toggle('high-contrast',settings.highContrast)
    document.documentElement.classList.toggle('reduce-motion',settings.reduceMotion)
    return()=>systemTheme.removeEventListener('change',applyTheme)
  },[settings])
  useEffect(()=>{
    const close=(event:MouseEvent)=>{const target=event.target as Node;if(!accountMenuRef.current?.contains(target)&&!sidebarProfileRef.current?.contains(target)&&!headerProfileRef.current?.contains(target))setAccountMenu(null)}
    document.addEventListener('mousedown',close)
    return()=>document.removeEventListener('mousedown',close)
  },[])
  const updateScheduleStatus=(status:ScheduleStatus)=>{
    setScheduleStatus(status)
    localStorage.setItem('flowsaic-schedule-status',status)
  }
  const go=(p:Page)=>{
    if(p==='Course Catalog') setCatalogFocus('')
    setPage(p)
    setSidebarOpen(false)
  }
  const openAccountPage=(destination:'My Profile'|'Scheduling Preferences'|'Settings'|'Help & Support')=>{if(!['My Profile','Scheduling Preferences','Settings','Help & Support'].includes(page))setAccountReturnPage(page);setPage(destination);setAccountMenu(null);setSidebarOpen(false)}
  const initials=profile.name.split(' ').map(part=>part[0]).join('').slice(0,2).toUpperCase()
  const openCourseInCatalog=(code:string)=>{setCatalogFocus(code);setPage('Course Catalog')}
  const addCourseToPlan=(code:string)=>{
    if(Object.values(plannedTerms).some(courses=>courses.includes(code))){
      setToast(`${code} is already in your roadmap`)
      return
    }
    const target=plannedTerms['Spring 2026']?'Spring 2026':Object.keys(plannedTerms).find(term=>term!==completedTermName&&term!==currentTermName)||'Spring 2026'
    setPlannedTerms({...plannedTerms,[target]:[...(plannedTerms[target]||[]),code]})
    setToast(`${code} added to ${target}`)
  }
  const toggleCoursePlan=(code:string)=>{
    const plannedEntry=Object.entries(plannedTerms).find(([term,courses])=>term!==completedTermName&&term!==currentTermName&&courses.includes(code))
    if(plannedEntry){
      setPlannedTerms(Object.fromEntries(Object.entries(plannedTerms).map(([term,courses])=>[term,term===plannedEntry[0]?courses.filter(item=>item!==code):courses])))
      setToast(`${code} removed from your roadmap`)
    } else addCourseToPlan(code)
  }
  const openCourseSchedule=(code:string)=>{
    const course=courseCatalog.find(item=>item.code===code)
    if(!course)return
    const plannedEntry=Object.entries(plannedTerms).find(([term,courses])=>term!==completedTermName&&term!==currentTermName&&courses.includes(code))
    const term=plannedEntry?.[0]||'Spring 2026'
    if(!plannedEntry)addCourseToPlan(code)
    const termCourses=Array.from(new Set([...(plannedTerms[term]||[]),code]))
    const sections=Object.fromEntries(termCourses.flatMap(courseCode=>{const item=courseCatalog.find(candidate=>candidate.code===courseCode);return item?[[courseCode,item.sections[0].id]]:[]}))
    localStorage.setItem('flowsaic-schedule-draft',JSON.stringify({selectedSections:sections,sectionChoices:sections,showCommitments:true,term}))
    setPage('Create Schedule')
  }
  const openTermSchedule=(codes:string[],term:string)=>{
    const sections=Object.fromEntries(codes.flatMap(code=>{const course=courseCatalog.find(item=>item.code===code);return course?[[code,course.sections[0].id]]:[]}))
    localStorage.setItem('flowsaic-schedule-draft',JSON.stringify({selectedSections:sections,sectionChoices:sections,showCommitments:true,term}))
    setToast(`${term} sent to Create Schedule`)
    setPage('Create Schedule')
  }
  const askFlowFromDashboard=(question:string)=>{
    const normalized=question.toLowerCase()
    const topic:AdvisorTopic=normalized.includes('schedule')?'schedule':normalized.includes('graduate')||normalized.includes('track')?'degree':normalized.includes('course')||normalized.includes('next')?'semester':'courses'
    const futureEntries=Object.entries(plannedTerms).filter(([term])=>term!==completedTermName&&term!==currentTermName)
    const plannedCodes=futureEntries.flatMap(([,courses])=>courses)
    const planCredits=plannedCodes.reduce((total,code)=>total+(courseCatalog.find(course=>course.code===code)?.credits||3),0)
    const latestTerm=futureEntries.filter(([,courses])=>courses.length).at(-1)?.[0]||'an unplanned term'
    const fixedCommitmentCount=calendarEvents.filter(event=>event.type==='Personal commitment'&&event.fixed).length
    const responses:Record<AdvisorTopic,string>={
      degree:`You have 82 confirmed credits and ${planCredits} credits in your roadmap through ${latestTerm}. Planned courses are estimates—not completed records—but your current sequence keeps the graduation projection aligned with the roadmap. I can review each outstanding requirement next.`,
      requirements:'Your remaining requirements include two Computer Science core courses, one mathematics requirement, three Design minor courses, and approved electives. CS 365 should be completed before CS 430.',
      semester:`Your roadmap currently includes ${plannedCodes.join(', ')||'no future courses yet'}. I’ll validate prerequisites in term order and keep each semester near 12–18 credits while preserving your graduation timing.`,
      courses:'CS 410 is a strong next option because CS 301 is complete. I can compare available sections, instructors, and meeting times or weigh it against other Spring 2026 courses.',
      schedule:`I can turn any planned term into a section-level schedule. Your roadmap currently carries ${planCredits} future credits; I’ll compare available sections against enrolled classes and ${fixedCommitmentCount} fixed personal commitments before recommending one.`,
    }
    setFlowStarted(true)
    setFlowMessages(current=>[...current,{role:'user',text:question},{role:'ai',text:responses[topic],topic,schedule:topic==='schedule'}])
    setPage('AI Advisor')
  }
  const openFlowSchedule=()=>{
    const sections={'CS 410':'001','CS 365':'002','MATH 310':'001','ENG 330':'001'}
    localStorage.setItem('flowsaic-schedule-draft',JSON.stringify({selectedSections:sections,sectionChoices:sections,showCommitments:true}))
    updateScheduleStatus('Draft Saved')
    setPage('Create Schedule')
  }
  const openSavedSchedule=()=>{
    if(!localStorage.getItem('flowsaic-schedule-draft')){
      const sections={'CS 410':'001','CS 365':'002','MATH 310':'001','ENG 330':'001'}
      localStorage.setItem('flowsaic-schedule-draft',JSON.stringify({selectedSections:sections,sectionChoices:sections,showCommitments:true}))
    }
    setPage('Create Schedule')
  }
  const askFlowAboutCalendar=()=>{
    const commitments=calendarEvents.filter(event=>event.type==='Personal commitment')
    const fixed=commitments.filter(event=>event.fixed)
    const openDays=(['Mon','Tue','Wed','Thu','Fri'] as CalendarEvent['day'][]).filter(day=>!fixed.some(event=>event.day===day))
    const context=`My calendar currently has ${calendarEvents.length} events: ${calendarEvents.filter(event=>event.category==='Academic').length} classes and ${commitments.length} personal commitments. ${fixed.length} commitments are fixed. Help me plan around them.`
    const response=`I reviewed your current calendar with ${calendarEvents.filter(event=>event.category==='Academic').length} academic meetings and ${commitments.length} personal commitments. I’ll treat ${fixed.length} fixed commitments as unavailable time when comparing courses. ${openDays.length?`${openDays.join(', ')} currently have the most flexibility.`:'Each weekday has at least one fixed block, so I’ll prioritize open gaps and avoid back-to-back conflicts.'} What would you like to plan?`
    setFlowStarted(true)
    setFlowMessages(current=>[...current,{role:'user',text:context},{role:'ai',text:response,topic:'schedule'}])
    setPage('AI Advisor')
  }
  const title=page==='Dashboard'?'Overview':page
  if(signedOut)return <main className="signed-out-screen"><section className="card login-card"><span className="top-brand-symbol"><img src="/assets/flow-koi.png" alt="Flowsaic koi"/></span><span className="eyebrow">FLOWSAIC</span><h1>Welcome back</h1><p>You have been signed out of the prototype. Your saved plans and preferences are still available on this device.</p><button className="primary" onClick={()=>setSignedOut(false)}>Sign in as {profile.name}</button><small>No password is required for this interactive prototype.</small></section></main>
  return <div className="app">
    <aside className={`sidebar ${sidebarOpen?'open':''} ${sidebarCollapsed?'collapsed':''}`}>
      <div className="brand"><button className="sidebar-collapse" aria-label={sidebarCollapsed?'Expand navigation':'Collapse navigation'} onClick={()=>setSidebarCollapsed(value=>!value)}><Icon name="arrow" size={16}/></button></div>
      <nav>{nav.slice(0,5).map(n=><button className={page===n.label?'active':''} key={n.label} onClick={()=>go(n.label)}><Icon name={n.icon}/><span>{n.label}</span></button>)}<div className="nav-section-label"><span>PLANNING TOOLS</span></div>{nav.slice(5).map(n=><button className={page===n.label?'active':''} key={n.label} onClick={()=>go(n.label)}><Icon name={n.icon}/><span>{n.label}</span>{n.label==='AI Advisor'&&<em>AI</em>}</button>)}</nav>
      <button ref={sidebarProfileRef} className={`profile ${accountMenu==='sidebar'?'menu-open':''}`} onClick={()=>setAccountMenu(current=>current==='sidebar'?null:'sidebar')} aria-expanded={accountMenu==='sidebar'}>{profile.photo?<img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name}/>:<div className="avatar">{initials}</div>}<span><strong>{profile.name}</strong><small>{profile.major}</small></span><Icon name="arrow" size={15}/></button>
    </aside>
    <main>
      <header><div className="header-left"><button className="mobile-menu" onClick={()=>setSidebarOpen(!sidebarOpen)}><Icon name="menu"/></button><button className="top-brand" onClick={()=>go('Dashboard')}><span style={{fontSize:25}}>flowsaic</span></button><i className="header-divider"/><span className="breadcrumb">Workspace /</span> <strong>{title}</strong></div><button className="search"><Icon name="search"/><span>Search courses, plans, and schedules</span></button><div className="header-actions"><button className="notify"><Icon name="bell"/><i/></button><button ref={headerProfileRef} className={`header-profile ${accountMenu==='header'?'menu-open':''}`} onClick={()=>setAccountMenu(current=>current==='header'?null:'header')} aria-expanded={accountMenu==='header'}>{profile.photo?<img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name}/>:<div className="avatar">{initials}</div>}<span><strong>{profile.name.split(' ')[0]}</strong><small>Student</small></span><Icon name="arrow" size={13}/></button></div></header>
      <div className="canvas">
        {page==='Dashboard'&&<Dashboard go={go} calendarEvents={calendarEvents} onAddEvent={event=>setCalendarEvents(current=>[...current,event])} scheduleStatus={scheduleStatus} askFlow={askFlowFromDashboard} viewSchedule={openSavedSchedule} studentName={profile.name}/>}
        {page==='Degree Progress'&&<><section className="page-title"><div><span className="eyebrow">ACADEMIC OVERVIEW</span><h1 className="degree-page-title">Your degree progress</h1><p className="degree-page-subtitle">Track every requirement on your path to graduation.</p></div></section><DegreePage plannedTerms={plannedTerms} openCatalog={openCourseInCatalog} addToPlan={addCourseToPlan} askFlow={askFlowFromDashboard}/></>}
        {page==='Course Catalog'&&<><section className="page-title catalog-page-title"><div><span className="eyebrow">EXPLORE COURSES</span><h1>Course catalog</h1><p>Find classes that fit your goals and your schedule.</p></div></section><Catalog focusCode={catalogFocus} plannedTerms={plannedTerms} togglePlan={toggleCoursePlan} openSchedule={openCourseSchedule} calendarEvents={calendarEvents}/></>}
        {page==='Semester Planner'&&<><section className="page-title"><div><span className="eyebrow">YOUR ROADMAP</span><h1 style={{fontSize:36}}>Semester planner</h1><p style={{fontSize:16}}>Drag courses to map out your path to graduation.</p></div></section><Planner plannedTerms={plannedTerms} setPlannedTerms={setPlannedTerms} openCatalog={openCourseInCatalog} openSchedule={openTermSchedule} askFlow={askFlowFromDashboard} preferences={preferences}/></>}
        {page==='My Calendar'&&<><section className="page-title"><div><span className="eyebrow">YOUR WEEK</span><h1 style={{fontSize:36}}>My calendar</h1><p style={{fontSize:16}}>Classes, work, and life — all in one place.</p></div></section><CalendarPage events={calendarEvents} onAdd={event=>setCalendarEvents(current=>[...current,event])} onUpdate={event=>setCalendarEvents(current=>current.map(item=>item.id===event.id?event:item))} onRemove={id=>setCalendarEvents(current=>current.filter(event=>event.id!==id))} askFlow={askFlowAboutCalendar}/></>}
        {page==='Create Schedule'&&<><section className="page-title create-schedule-title"><div><span className="eyebrow">SCHEDULE BUILDER</span><h1>Create your schedule</h1><p>Search courses, build your week, or let Flowsaic create a balanced schedule for you.</p></div></section><CreateSchedule saveDraft={()=>{updateScheduleStatus('Draft Saved');setToast('Draft saved — you can continue editing anytime')}} submit={()=>{updateScheduleStatus('Pending Approval');setToast('Schedule submitted to Dr. Chen for approval')}} askAdvisor={()=>go('AI Advisor')} openPreferences={()=>openAccountPage('Scheduling Preferences')} calendarEvents={calendarEvents} plannedTerms={plannedTerms} preferences={preferences}/></>}
        {page==='AI Advisor'&&<><section className="page-title ai-advisor-title"><div><span className="eyebrow">PERSONALIZED GUIDANCE</span><h1>Meet Flow, your AI advisor</h1><p>Friendly guidance grounded in your degree plan, courses, and commitments.</p></div></section><AIAdvisor messages={flowMessages} onMessagesChange={setFlowMessages} started={flowStarted} onStartedChange={setFlowStarted} openSchedule={openFlowSchedule} plannedTerms={plannedTerms} calendarEvents={calendarEvents} preferences={preferences} studentName={profile.name}/></>}
        {page==='Advisor Dashboard'&&<><section className="page-title"><div><span className="eyebrow">ADVISOR WORKSPACE</span><h1>Student schedule reviews</h1><p>Review plans, share feedback, and keep students on track.</p></div></section><article className="card review"><div className="avatar">{initials}</div><div><h2>{profile.name}</h2><p>Spring 2026 · 13 credits · Submitted 2 hours ago</p></div><span className="pill orange">Pending review</span><button className="ghost" onClick={()=>setToast(`Revision request sent to ${profile.name.split(' ')[0]}`)}>Request revision</button><button className="primary" onClick={()=>{updateScheduleStatus('Approved');setToast(`${profile.name.split(' ')[0]}’s schedule was approved`)}}>Approve schedule</button></article></>}
        {page==='My Profile'&&<><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>My profile</h1><p style={{fontSize:16}}>Manage your student information and review your academic summary.</p></div><button className="ghost account-back" onClick={()=>go(accountReturnPage)}><span className="previous-arrow"><Icon name="arrow" size={15}/></span>Back to {accountReturnPage==='Dashboard'?'Overview':accountReturnPage}</button></section><ProfilePage profile={profile} onPhotoSave={photo=>{setProfile({...officialStudentProfile,photo});setToast(photo?'Profile photo updated':'Profile photo removed')}} go={go}/></>}
        {page==='Scheduling Preferences'&&<><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>Scheduling preferences</h1><p>Tell Flowsaic how to prioritize sections and build your schedule.</p></div><button className="ghost account-back" onClick={()=>go(accountReturnPage)}><span className="previous-arrow"><Icon name="arrow" size={15}/></span>Back to {accountReturnPage==='Dashboard'?'Overview':accountReturnPage}</button></section><SchedulingPreferencesPage preferences={preferences} onSave={setPreferences} onNotify={setToast}/></>}
        {page==='Settings'&&<><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>Settings</h1><p>Manage notifications, appearance, privacy, and accessibility.</p></div><button className="ghost account-back" onClick={()=>go(accountReturnPage)}><span className="previous-arrow"><Icon name="arrow" size={15}/></span>Back to {accountReturnPage==='Dashboard'?'Overview':accountReturnPage}</button></section><SettingsPage settings={settings} onSave={setSettings} onNotify={setToast} profile={profile} onAppearanceChange={appearance=>setSettings(current=>({...current,appearance}))}/></>}
        {page==='Help & Support'&&<><section className="page-title account-page-title"><div><span className="eyebrow">SUPPORT</span><h1>Help & Support</h1><p>Find answers and get help with Flowsaic.</p></div><button className="ghost account-back" onClick={()=>go(accountReturnPage)}><span className="previous-arrow"><Icon name="arrow" size={15}/></span>Back to {accountReturnPage==='Dashboard'?'Overview':accountReturnPage}</button></section><HelpSupportPage onNotify={setToast}/></>}
      </div>
    </main>
    {accountMenu&&<div ref={accountMenuRef} className={`profile-popover ${accountMenu}-anchor ${sidebarCollapsed?'rail-collapsed':''}`} role="menu"><div className="profile-popover-head">{profile.photo?<img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name}/>:<div className="avatar">{initials}</div>}<div><strong>{profile.name}</strong><small>{profile.major}</small></div></div><div className="profile-menu-list"><button role="menuitem" onClick={()=>openAccountPage('My Profile')}><span className="feature-icon blue"><Icon name="user" size={17}/></span><span>My Profile</span></button><button role="menuitem" onClick={()=>openAccountPage('Scheduling Preferences')}><span className="feature-icon purple"><Icon name="sliders" size={17}/></span><span>Scheduling Preferences</span></button><button role="menuitem" onClick={()=>openAccountPage('Settings')}><span className="feature-icon teal"><Icon name="settings" size={17}/></span><span>Settings</span></button><button role="menuitem" onClick={()=>openAccountPage('Help & Support')}><span className="feature-icon orange"><Icon name="help" size={17}/></span><span>Help & Support</span></button><button role="menuitem" className="sign-out-item" onClick={()=>{setAccountMenu(null);setSignOutConfirm(true)}}><span className="feature-icon pink"><Icon name="logout" size={17}/></span><span>Sign Out</span></button></div></div>}
    <nav className="mobile-bottom-nav">{(['Dashboard','Degree Progress','Semester Planner','My Calendar','AI Advisor'] as Page[]).map(item=>{const itemData=nav.find(entry=>entry.label===item)!;return <button className={page===item?'active':''} key={item} onClick={()=>go(item)}><Icon name={itemData.icon} size={19}/><span>{item==='Degree Progress'?'Degree':item==='Semester Planner'?'Plan':item==='My Calendar'?'Calendar':item==='AI Advisor'?'Flow':'Home'}</span></button>})}</nav>
    {signOutConfirm&&<div className="modal-backdrop" onMouseDown={()=>setSignOutConfirm(false)}><section className="event-dialog sign-out-dialog" onMouseDown={event=>event.stopPropagation()}><span className="feature-icon pink"><Icon name="logout"/></span><h2>Sign out of Flowsaic?</h2><p>Your plans, preferences, and prototype data will remain saved on this device.</p><div className="event-dialog-actions"><button className="ghost" onClick={()=>setSignOutConfirm(false)}>Cancel</button><button className="sign-out-confirm" onClick={()=>{setSignOutConfirm(false);setSignedOut(true)}}>Sign out</button></div></section></div>}
    {toast&&<div className="toast"><span className="soft-icon mint"><Icon name="check"/></span>{toast}<button onClick={()=>setToast('')}>Dismiss</button></div>}
  </div>
}

export default App
