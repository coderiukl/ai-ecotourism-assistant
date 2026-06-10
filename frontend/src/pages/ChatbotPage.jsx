import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Bot, Send } from 'lucide-react';

import { API_URL } from '../api';

function isSafeUrl(url) {
  return /^(https?:\/\/|mailto:|tel:)/i.test(url);
}

function renderInline(text, keyPrefix) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^\s)]+\)|\$[^$]+\$|\\\([\s\S]+?\\\)|https?:\/\/[^\s<)]+)/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));

    const token = match[0];
    const key = `${keyPrefix}-${parts.length}`;

    if (token.startsWith('**')) {
      parts.push(<strong key={key}>{renderInline(token.slice(2, -2), key)}</strong>);
    } else if (token.startsWith('`')) {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('[')) {
      const link = token.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/);
      const href = link?.[2] || '';
      parts.push(
        isSafeUrl(href) ? (
          <a href={href} key={key} rel="noreferrer" target="_blank">
            {link[1]}
          </a>
        ) : (
          link?.[1] || token
        ),
      );
    } else if (token.startsWith('$')) {
      parts.push(<span className="math-inline" key={key}>{token.slice(1, -1)}</span>);
    } else if (token.startsWith('\\(')) {
      parts.push(<span className="math-inline" key={key}>{token.slice(2, -2)}</span>);
    } else {
      const href = token.replace(/[.,;:!?]+$/, '');
      parts.push(
        <a href={href} key={key} rel="noreferrer" target="_blank">
          {href}
        </a>,
      );
      if (href.length < token.length) parts.push(token.slice(href.length));
    }

    lastIndex = match.lastIndex;
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function normalizeMarkdownText(text) {
  const raw = String(text || '')
    .replace(/\r\n?/g, '\n')
    .trim()
    .replace(/\s*•\s+/g, '\n- ')
    .replace(/([^\n])\s+([-*]\s+)/g, '$1\n$2');

  const lines = raw.split('\n').map((line) => line.trim()).filter(Boolean);
  const isListLine = (line) => /^(?:[-*]|•)\s+/.test(line) || /^\d+\.\s+/.test(line);
  const grouped = [];

  lines.forEach((line) => {
    const prev = grouped[grouped.length - 1];
    if (prev && isListLine(prev) !== isListLine(line)) grouped.push('');
    grouped.push(line);
  });

  return grouped.join('\n');
}

function MarkdownMessage({ text }) {
  const blocks = normalizeMarkdownText(text).split(/\n{2,}/);

  return (
    <div className="markdown-message">
      {blocks.map((block, index) => {
        const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
        const key = `block-${index}`;

        if (!lines.length) return null;

        if (/^\$\$[\s\S]*\$\$$/.test(block.trim())) {
          return <div className="math-block" key={key}>{block.trim().slice(2, -2).trim()}</div>;
        }

        if (lines.every((line) => /^[-*]\s+/.test(line)) || lines.every((line) => /^•\s+/.test(line))) {
          return (
            <ul key={key}>
              {lines.map((line, itemIndex) => {
                const clean = line.replace(/^[-*]\s+/, '').replace(/^•\s+/, '');
                return <li key={`${key}-${itemIndex}`}>{renderInline(clean, `${key}-${itemIndex}`)}</li>;
              })}
            </ul>
          );
        }

        if (lines.every((line) => /^\d+\.\s+/.test(line))) {
          return (
            <ol key={key}>
              {lines.map((line, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(line.replace(/^\d+\.\s+/, ''), `${key}-${itemIndex}`)}</li>
              ))}
            </ol>
          );
        }

        if (lines.every((line) => /^>\s?/.test(line))) {
          return <blockquote key={key}>{renderInline(lines.map((line) => line.replace(/^>\s?/, '')).join(' '), key)}</blockquote>;
        }

        if (/^#{1,3}\s+/.test(lines[0])) {
          const level = lines[0].match(/^#+/)?.[0].length || 3;
          const content = lines[0].replace(/^#{1,3}\s+/, '');
          return level === 1 ? <h3 key={key}>{renderInline(content, key)}</h3> : <h4 key={key}>{renderInline(content, key)}</h4>;
        }

        return <p key={key}>{renderInline(lines.join(' '), key)}</p>;
      })}
    </div>
  );
}

export default function ChatbotPage({ destination, onBack, onDone }) {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: `Xin chào! Mình là AI Guide. Bạn có thể hỏi mình về ${destination?.name || 'địa điểm này'}.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [visibleStreamingText, setVisibleStreamingText] = useState('');
  const chatBoxRef = useRef(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const prevLoadingRef = useRef(false);
  const sessionIdRef = useRef(`session_${destination?.id || 'default'}_${Date.now()}`);

  useEffect(() => {
    if (!loading && prevLoadingRef.current) {
      setStreamingText('');
      setVisibleStreamingText('');
    }
    prevLoadingRef.current = loading;
  }, [loading]);

  const scrollToBottom = (behavior = 'smooth') => {
    const box = chatBoxRef.current;
    if (box) {
      box.scrollTo({ top: box.scrollHeight, behavior });
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior, block: 'end' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, visibleStreamingText]);

  useEffect(() => {
    if (!loading) {
      setVisibleStreamingText('');
      return;
    }
    if (visibleStreamingText.length >= streamingText.length) return;

    const timer = window.setTimeout(() => {
      const nextLength = Math.min(streamingText.length, visibleStreamingText.length + 3);
      setVisibleStreamingText(streamingText.slice(0, nextLength));
    }, 18);

    return () => window.clearTimeout(timer);
  }, [loading, streamingText, visibleStreamingText]);

  useEffect(() => {
    if (!loading && streamingText) {
      setStreamingText('');
      setVisibleStreamingText('');
    }
    inputRef.current?.focus();
  }, [messages, loading]);

  async function ask(question = input) {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || loading) return;

    setMessages((prev) => [...prev, { role: 'user', text: cleanQuestion }]);
    setInput('');
    setLoading(true);
    setStreamingText('');
    setVisibleStreamingText('');

    const sessionId = sessionIdRef.current;

    async function askWithoutStream() {
      const fallbackRes = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination_id: destination?.id || 1,
          message: cleanQuestion,
          session_id: sessionId,
        }),
      });

      if (!fallbackRes.ok) throw new Error(`HTTP ${fallbackRes.status}`);
      const data = await fallbackRes.json();
      return data.answer || 'AI chưa có câu trả lời phù hợp.';
    }

    try {
      const res = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination_id: destination?.id || 1,
          message: cleanQuestion,
          session_id: sessionId,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let botText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('event: token')) continue;
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) {
                botText += data.token;
                setStreamingText(botText);
                setVisibleStreamingText(botText);
                scrollToBottom('auto');
              }
            } catch {}
          }
          if (line.startsWith('event: done')) break;
        }
      }

      if (botText) setMessages((prev) => [...prev, { role: 'bot', text: botText }]);
    } catch (e) {
      try {
        const answer = await askWithoutStream();
        setMessages((prev) => [...prev, { role: 'bot', text: answer }]);
        setLoading(false);
        setStreamingText('');
        return;
      } catch (fallbackError) {
        console.error('Chat backend error', {
          apiUrl: API_URL || window.location.origin,
          streamError: e,
          fallbackError,
        });
      }
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: 'Hiện tại AI chưa kết nối được backend. Bạn thử lại sau nhé.' },
      ]);
    }

    setLoading(false);
    setStreamingText('');
  }

  return (
    <div className="phone">
      <div className="page chatbot-page">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> Địa điểm
        </button>

        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              <Bot size={15} /> AI Chatbot
            </div>
            <h2>Hỏi AI Guide</h2>
          </div>
        </div>

        <div className="quick-questions">
          <button onClick={() => ask('Có gì chơi ở đây?')}>Có gì chơi?</button>
          <button onClick={() => ask('Đi mùa nào đẹp?')}>Đi mùa nào đẹp?</button>
          <button onClick={() => ask('Có phù hợp cho gia đình không?')}>Phù hợp gia đình?</button>
        </div>

        <div className="chat-box" aria-live="polite" ref={chatBoxRef}>
          {messages.map((message, index) => (
            <div className={`msg ${message.role === 'user' ? 'user' : 'bot'}`} key={index}>
              <MarkdownMessage text={message.text} />
            </div>
          ))}
          {loading && (
            <div className="msg bot streaming-bubble">
              <MarkdownMessage text={visibleStreamingText || ' '} />
              <span className="typing-cursor" />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form className="chat-input" onSubmit={(event) => { event.preventDefault(); ask(); }}>
          <input
            disabled={loading}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Nhập câu hỏi..."
            ref={inputRef}
            value={input}
          />
          <button aria-label="Gửi câu hỏi" disabled={loading || !input.trim()} type="submit">
            <Send size={18} />
          </button>
        </form>

        <div style={{ height: 12 }} />

        <button className="primary-btn" onClick={onDone}>
          Hoàn tất trải nghiệm
        </button>
      </div>
    </div>
  );
}
