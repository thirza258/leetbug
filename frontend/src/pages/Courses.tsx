import { ArrowLeft, ArrowRight, BookOpen, Bug, Check, CheckCircle2, Clock3, ExternalLink } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { EmptyState, PageHeading } from '../components/ui';
import { useAuth } from '../lib/auth';
import { categories } from '../lib/constants';
import { courseMinutes, courses, courseTracks, lessonKey } from '../lib/courses';
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
  const [params] = useSearchParams();
  const selectedTrack = courseTracks.find(track => track.id === params.get('track'));
  const visibleCourses = selectedTrack ? courses.filter(course => course.track === selectedTrack.id) : courses;
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
    <PageHeading eyebrow="LEARN, THEN PRACTICE" title="Problem-solving courses"
      description="Learn how to find the bug, choose a system design, and prove your fix. Follow practical lessons for every problem category."
      action={<Link className="button secondary" to="/">Explore practice problems <ArrowRight size={16} /></Link>} />
    <nav className="course-track-filters" aria-label="Course sections">
      <Link to="/courses" aria-current={!selectedTrack ? 'page' : undefined}>All courses <span>{courses.length}</span></Link>
      {courseTracks.map(track => <Link key={track.id} to={`/courses?track=${track.id}`} aria-current={selectedTrack?.id === track.id ? 'page' : undefined}>{track.title}<span>{courses.filter(course => course.track === track.id).length}</span></Link>)}
    </nav>
    <div className="course-intro" role="status"><BookOpen size={21} /><p>{visibleCourses.length} courses · {visibleCourses.reduce((total, course) => total + course.lessons.length, 0)} lessons · Worked examples and a knowledge check in every lesson</p></div>
    {(selectedTrack ? [selectedTrack] : courseTracks).map(track => {
      const Icon = track.id === 'debugging' ? Bug : categories[track.id].icon;
      return <section className="course-track" key={track.id} aria-labelledby={`track-${track.id}`}>
        <div className="course-track-heading"><div><h2 id={`track-${track.id}`}><Icon size={22} />{track.title}</h2><p>{track.description}</p></div>
          {track.id !== 'debugging' && <Link className="text-link" to={`/?category=${track.id}`}>Practice this section <ArrowRight size={15} /></Link>}
        </div>
        <div className="course-grid">{visibleCourses.filter(course => course.track === track.id).map(course => <CourseCard key={course.slug} course={course} completed={completed} />)}</div>
      </section>;
    })}
    <p className="course-storage-note" role="status">{progressNote}</p>
    <section className="surface course-practice-banner"><div><span className="eyebrow">PUT IT INTO PRACTICE</span><h2>Turn your next failure into a fix</h2><p>Choose a problem, reproduce the failure, and apply the method you learned.</p></div><Link className="button secondary" to="/">Browse case studies <ArrowRight size={16} /></Link></section>
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
          <section className="lesson-example"><span className="eyebrow">WORKED EXAMPLE</span><h3>{lesson.example.title}</h3><p>{lesson.example.text}</p>
            {lesson.example.code && <figure className="lesson-code"><figcaption>{lesson.example.code.label}</figcaption><pre tabIndex={0} aria-label={lesson.example.code.label}><code>{lesson.example.code.text}</code></pre></figure>}
            {lesson.example.steps && <ol className="lesson-steps" aria-label="Worked example steps">{lesson.example.steps.map(step => <li key={step}>{step}</li>)}</ol>}
          </section>
          <a className="text-link lesson-source" href={lesson.source.url} target="_blank" rel="noreferrer">{lesson.source.title}<ExternalLink size={14} /><span className="sr-only"> (opens in a new tab)</span></a>
        </article>
        <Checkpoint key={lessonKey(course, lesson)} lesson={lesson} completed={completed.has(lessonKey(course, lesson))} onComplete={() => completeLesson(lessonKey(course, lesson))} />
        <div className="lesson-pagination">{index > 0 && <Link className="button secondary" to={`/courses/${course.slug}/${course.lessons[index - 1].slug}`}><ArrowLeft size={15} />Previous lesson</Link>}{nextLesson && <Link className="button primary" to={`/courses/${course.slug}/${nextLesson.slug}`}>Next lesson<ArrowRight size={15} /></Link>}</div>
        {done === course.lessons.length && <section className="surface course-complete" role="status"><CheckCircle2 className="green" size={25} /><h2>Course complete</h2><p>You passed every knowledge check. Apply what you learned in a case study.</p>{nextCourse && <Link className="text-link" to={`/courses/${nextCourse.slug}`}>Next course: {nextCourse.title}<ArrowRight size={15} /></Link>}</section>}
        <section className="surface course-practice"><h2>Practice with case studies</h2><p>Apply this method to a buggy program, then run the tests to check your reasoning.</p>{course.practice.map(problem => <Link className="practice-link" key={problem.slug} to={`/problems/${problem.slug}`}>{problem.title}<ArrowRight size={16} /></Link>)}<Link className="text-link course-section-link" to={`/courses?track=${course.track}`}>More courses in this section <ArrowRight size={15} /></Link></section>
      </div>
    </div>
  </div>;
}

function CourseCard({ course, completed }: { course: Course; completed: Set<string> }) {
  const done = course.lessons.filter(lesson => completed.has(lessonKey(course, lesson))).length;
  const next = course.lessons.find(lesson => !completed.has(lessonKey(course, lesson))) || course.lessons[0];
  return <article className="surface course-card">
    <div className="course-card-top"><span className="eyebrow">COURSE {String(courses.indexOf(course) + 1).padStart(2, '0')}</span><span className="course-level">{course.level}</span></div>
    <h3><Link to={`/courses/${course.slug}`}>{course.title}</Link></h3><p>{course.description}</p>
    <div className="course-meta"><span><BookOpen size={14} />{course.lessons.length} lessons</span><span><Clock3 size={14} />About {courseMinutes(course)} min</span></div>
    <ul className="course-outcomes">{course.outcomes.map(outcome => <li key={outcome}><Check size={14} />{outcome}</li>)}</ul>
    <div className="course-card-bottom"><CourseProgress course={course} done={done} /><Link className="button primary full" to={`/courses/${course.slug}/${next.slug}`}>{done === course.lessons.length ? 'Review course' : done ? 'Continue course' : 'Start course'}<ArrowRight size={15} /></Link></div>
  </article>;
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
    {answer && <div className={`checkpoint-feedback ${answer.correct ? 'correct' : 'incorrect'}`} role="status"><strong>{answer.correct ? 'Well reasoned.' : 'Follow the evidence and try again.'}</strong><p>{answer.feedback}</p></div>}
  </section>;
}
