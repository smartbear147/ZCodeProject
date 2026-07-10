export interface SubtitleLine {
  text: string;
  isFinal: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  doc_type: 'resume' | 'qa';
  size_bytes: number;
}
