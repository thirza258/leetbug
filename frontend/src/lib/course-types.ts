import type { Category } from '../types';

export type CourseTrack = 'debugging' | Category;

export interface Lesson {
  slug: string;
  title: string;
  minutes: number;
  sections: { title: string; text: string }[];
  example: {
    title: string;
    text: string;
    code?: { label: string; text: string };
    steps?: string[];
  };
  checkpoint: {
    question: string;
    options: { text: string; correct?: true; feedback: string }[];
  };
  source: { title: string; url: string };
}

export interface Course {
  slug: string;
  track: CourseTrack;
  title: string;
  description: string;
  level: 'Foundations' | 'Intermediate';
  outcomes: string[];
  lessons: Lesson[];
  practice: { slug: string; title: string }[];
}
