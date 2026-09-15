import { ArrowLeft, ArrowRight, BookOpen, Check, CheckCircle2, Clock3, ExternalLink, Network } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { EmptyState, PageHeading } from '../components/ui';
import { useAuth } from '../lib/auth';
import { courseMinutes, courses, lessonKey } from '../lib/courses';
import type { Course, Lesson } from '../lib/courses';
import './courses.css';

const knownLessons = new Set(courses.flatMap(course => course.lessons.map(lesson => lessonKey(course, lesson))));

function readCompleted(storageKey: string): Set<string> {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return new Set(Array.isArray(saved) ? saved.filter((key): key is string => typeof key === 'string' && knownLessons.has(key)) : []);
  } catch { return new Set(); }
}

export default function Courses() {
  const { user } = useAuth();
  const storageKey = `leetbug.courses.v1:${user?.id || 'guest'}`;
  return <CoursesContent key={storageKey} storageKey={storageKey} />;
}

function CoursesContent({ storageKey }: { storageKey: string }) {
  const { courseSlug, lessonSlug } = useParams();
  const [completed, setCompleted] = useState(() => readCompleted(storageKey));
  const [storageFailed, setStorageFailed] = useState(false);
  const progressNote = storageFailed
    ? 'Browser storage is unavailable. Progress will last until you leave this page.'
    : 'Knowledge checks save your course progress in this browser. Sign in before starting to keep it separate from guest progress.';

  function completeLesson(key: string) {
    const next = new Set([...readCompleted(storageKey), ...completed, key]);
    setCompleted(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify([...next]));
      setStorageFailed(false);
    } catch {
      setStorageFailed(true);
      toast.error('Progress could not be saved in this browser. You can keep learning.');
    }
  }

  if (!courseSlug) return <div className="page courses-page">
    <PageHeading eyebrow="LEARN, THEN PRACTICE" title="System design courses"
      description="Build a system you can explain. Start with requirements, understand the trade-offs, and put your choices to the test."
      action={<Link className="button secondary" to="/?category=system_design">Practice system design <ArrowRight size={16} /></Link>} />
    <div className="course-intro"><Network size={21} /><p>Three short courses · Nine lessons · Worked examples and a knowledge check in every lesson</p></div>
    <div className="course-grid">{courses.map((course, index) => {
      const done = course.lessons.filter(lesson => completed.has(lessonKey(course, lesson))).length;
      const next = course.lessons.find(lesson => !completed.has(lessonKey(course, lesson))) || course.lessons[0];
      return <article className="surface course-card" key={course.slug}>
        <div className="course-card-top"><span className="eyebrow">COURSE 0{index + 1}</span><span className="course-level">{course.level}</span></div>
        <h2><Link to={`/courses/${course.slug}`}>{course.title}</Link></h2><p>{course.description}</p>
        <div className="course-meta"><span><BookOpen size={14} />{course.lessons.length} lessons</span><span><Clock3 size={14} />About {courseMinutes(course)} min</span></div>
        <ul className="course-outcomes">{course.outcomes.map(outcome => <li key={outcome}><Check size={14} />{outcome}</li>)}</ul>
        <div className="course-card-bottom"><CourseProgress course={course} done={done} />
          <Link className="button primary full" to={`/courses/${course.slug}/${next.slug}`}>{done === course.lessons.length ? 'Review course' : done ? 'Continue course' : 'Start course'}<ArrowRight size={15} /></Link>
        </div>
      </article>;
    })}</div>
    <p className="course-storage-note" role="status">{progressNote}</p>
    <section className="surface course-practice-banner"><div><span className="eyebrow">PUT IT INTO PRACTICE</span><h2>Choosing the right system design</h2><p>Fix an architecture selector that favors throughput over the team’s actual requirements.</p></div><Link className="button secondary" to="/problems/choosing-the-right-system-design">Open case study <ArrowRight size={16} /></Link></section>
  </div>;

  const course = courses.find(item => item.slug === courseSlug);
  const lesson = course?.lessons.find(item => item.slug === (lessonSlug || course.lessons[0].slug));
  if (!course || !lesson) return <div className="page"><EmptyState title="This lesson could not be found."><p>Choose a course to continue learning.</p><Link className="button primary" to="/courses">Browse courses</Link></EmptyState></div>;
  const index = course.lessons.indexOf(lesson);
  const done = course.lessons.filter(item => completed.has(lessonKey(course, item))).length;
  const nextLesson = course.lessons[index + 1];
  const nextCourse = courses[courses.indexOf(course) + 1];

  return <div className="page course-detail-page">
    <Link className="text-link course-back" to="/courses"><ArrowLeft size={15} />All courses</Link>
    <PageHeading eyebrow={`${course.level.toUpperCase()} · ${course.lessons.length} LESSONS`} title={course.title} description={course.description} />
    <div className="course-layout">
      <aside className="surface course-outline"><h2>Course contents</h2><CourseProgress course={course} done={done} />
        <nav aria-label="Course lessons">{course.lessons.map((item, position) => <Link key={item.slug} to={`/courses/${course.slug}/${item.slug}`} aria-current={item === lesson ? 'page' : undefined} className={`lesson-link ${item === lesson ? 'active' : ''}`}>
          <span className={completed.has(lessonKey(course, item)) ? 'green' : 'muted'}>{completed.has(lessonKey(course, item)) ? <CheckCircle2 size={18} aria-label="Completed" /> : String(position + 1).padStart(2, '0')}</span><span>{item.title}<small>{item.minutes} min</small></span>
        </Link>)}</nav><p className="course-storage-note" role="status">{progressNote}</p>
      </aside>
      <div className="lesson-main">
        <article className="surface lesson-content"><span className="eyebrow">LESSON {index + 1} OF {course.lessons.length} · {lesson.minutes} MIN</span><h2>{lesson.title}</h2>
          {lesson.sections.map(section => <section key={section.title}><h3>{section.title}</h3><p>{section.text}</p></section>)}
          <section className="lesson-example"><span className="eyebrow">WORKED EXAMPLE</span><h3>{lesson.example.title}</h3><p>{lesson.example.text}</p></section>
          <a className="text-link lesson-source" href={lesson.source.url} target="_blank" rel="noreferrer">{lesson.source.title}<ExternalLink size={14} /><span className="sr-only"> (opens in a new tab)</span></a>
        </article>
        <Checkpoint key={lessonKey(course, lesson)} lesson={lesson} completed={completed.has(lessonKey(course, lesson))} onComplete={() => completeLesson(lessonKey(course, lesson))} />
        <div className="lesson-pagination">{index > 0 && <Link className="button secondary" to={`/courses/${course.slug}/${course.lessons[index - 1].slug}`}><ArrowLeft size={15} />Previous lesson</Link>}{nextLesson && <Link className="button primary" to={`/courses/${course.slug}/${nextLesson.slug}`}>Next lesson<ArrowRight size={15} /></Link>}</div>
        {done === course.lessons.length && <section className="surface course-complete" role="status"><CheckCircle2 className="green" size={25} /><h2>Course complete</h2><p>You passed every knowledge check. Apply what you learned in a case study.</p>{nextCourse && <Link className="text-link" to={`/courses/${nextCourse.slug}`}>Next course: {nextCourse.title}<ArrowRight size={15} /></Link>}</section>}
        <section className="surface course-practice"><h2>Practice with case studies</h2><p>Make the design principle concrete by repairing a working program.</p>{course.practice.map(problem => <Link className="practice-link" key={problem.slug} to={`/problems/${problem.slug}`}>{problem.title}<ArrowRight size={16} /></Link>)}</section>
      </div>
    </div>
  </div>;
}

function CourseProgress({ course, done }: { course: Course; done: number }) {
  return <div className="course-progress"><span>{done} of {course.lessons.length} lessons complete</span><progress aria-label={`${course.title} progress`} max={course.lessons.length} value={done} /></div>;
}

function Checkpoint({ lesson, completed, onComplete }: { lesson: Lesson; completed: boolean; onComplete: () => void }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [checked, setChecked] = useState<number | null>(null);
  const answer = checked === null ? null : lesson.checkpoint.options[checked];
  return <section className="surface lesson-checkpoint"><h2>Check your understanding</h2>
    {completed && <p className="checkpoint-completed"><CheckCircle2 size={16} />Knowledge check passed</p>}
    <form onSubmit={event => {
      event.preventDefault();
      if (selected === null) return;
      setChecked(selected);
      if (lesson.checkpoint.options[selected].correct) onComplete();
    }}><fieldset><legend>{lesson.checkpoint.question}</legend>{lesson.checkpoint.options.map((option, index) => <label className={`checkpoint-option ${selected === index ? 'selected' : ''}`} key={option.text}>
      <input type="radio" name={`checkpoint-${lesson.slug}`} value={index} checked={selected === index} onChange={() => { setSelected(index); setChecked(null); }} /><span>{option.text}</span>
    </label>)}</fieldset><button className="button primary" type="submit" disabled={selected === null}>Check answer<ArrowRight size={15} /></button></form>
    {answer && <div className={`checkpoint-feedback ${answer.correct ? 'correct' : 'incorrect'}`} role="status"><strong>{answer.correct ? 'Well reasoned.' : 'Revisit the trade-off.'}</strong><p>{answer.feedback}</p></div>}
  </section>;
}
