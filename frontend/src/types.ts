export interface SubtitleLine {
  text: string;
  isFinal: boolean;
}

export interface SuggestResult {
  sessionId: string;
  suggestion: string;
  question: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
