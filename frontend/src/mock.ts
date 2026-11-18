// MOCK DATA, clearly labelled. Nothing wired to the backend may read from this file.
// It feeds only the mock-only features (AGENTS.md): the Semester Planner (multiple terms), the
// Advisor Dashboard and the submit-for-approval status, professor ratings, and the
// notifications bell. Remove these as the real features arrive in semester 2.
import type { CalendarEvent, StudentProfile } from './types'

export type MockCourseSection = { id:string; schedule:string; instructor:string; room:string; meetings:{day:number;start:number;end:number}[]; seats:number; rating:number; reviews:number }
export type MockCourseRecord = {
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
  sections:MockCourseSection[]
}
export type PlannedTerms = Record<string,string[]>

/** MOCK: the Semester Planner's made-up catalog (not SAU courses). */
export const courseCatalog:MockCourseRecord[] = [
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

/** MOCK: the Semester Planner's made-up terms and record. */
export const currentTermCourses=['CS 301','ECON 210','DES 240','MATH 260','ENG 215']
export const completedTermName='Spring 2025'
export const currentTermName='Fall 2025'
export const completedCourseCodes=new Set(['CS 101','CS 201','CS 220','CS 250','CS 270','CS 280','MATH 210','MATH 220','MATH 240','MATH 250','DES 110','DES 120','ENG 101','ENG 102','PSY 101','HIST 110','BIO 105','COMM 120','SOC 101','ART 100','STAT 200','PHIL 210','SCI 115','CIV 100'])
export const initialPlannedTerms:PlannedTerms={
  [completedTermName]:['CS 220','MATH 240','DES 120','ENG 102'],
  [currentTermName]:currentTermCourses,
  'Spring 2026':['CS 410','CS 365','MATH 310','ENG 330'],
  'Summer 2026':['CS 430'],
  'Fall 2026':['CS 490','CS 420','DES 340'],
}

/** MOCK: the original prototype's sample student (no longer shown anywhere wired). */
export const mockStudentProfile:Omit<StudentProfile,'photo'>={name:'Maya Johnson',email:'mjohnson@muleriders.saumag.edu',university:'Southern Arkansas University',major:'Computer Science',minor:'Design',degree:'B.S. Computer Science',standing:'Good academic standing',graduation:'December 2026'}

/** MOCK: the original prototype's sample calendar (the real calendar uses /me/events). */
export const mockCalendarEvents: CalendarEvent[] = [
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

/** MOCK: professor ratings. There is no rating data yet, and made-up numbers next to real SAU
 * instructors would mislead, so real courses start with no reviews; "Rate this course" only
 * keeps a student's own rating on this page (not saved anywhere). */
export const mockRatingsEnabled=true

/** MOCK: the advisor who "approves" schedules in the Advisor Dashboard. */
export const mockAdvisorName='Dr. Chen'
