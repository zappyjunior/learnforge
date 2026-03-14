import json
from openai import OpenAI

MODEL = "gpt-4o-mini"
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="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"
        )
    return _client


def generate_course(topic, difficulty="intermediate"):
    difficulty_guide = {
        "beginner": "Assume no prior knowledge. Use simple language, lots of analogies, and very basic examples. Build up slowly from fundamentals.",
        "intermediate": "Assume basic familiarity with the subject area. Cover concepts in moderate depth with practical examples.",
        "advanced": "Assume solid foundational knowledge. Go deep into advanced patterns, edge cases, performance considerations, and real-world architecture."
    }.get(difficulty, "")

    prompt = f"""Create a structured learning course on the topic: "{topic}"
Difficulty level: {difficulty}. {difficulty_guide}

Return a JSON object with this exact structure:
{{
    "title": "Course title",
    "description": "Brief course description (1-2 sentences)",
    "lessons": [
        {{
            "title": "Lesson title",
            "content": "Detailed lesson content in markdown format (5-8 paragraphs). Explain each concept clearly, then show practical code examples demonstrating how to use it. Balance theory with hands-on — the student should understand both WHAT something is and HOW to use it.",
            "quiz": [
                {{
                    "type": "multiple_choice",
                    "question": "Question text",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "The correct option text exactly as in options",
                    "explanation": "Why this is correct"
                }},
                {{
                    "type": "multiple_choice",
                    "question": "Question text",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "The correct option text exactly as in options",
                    "explanation": "Why this is correct"
                }},
                {{
                    "type": "short_answer",
                    "question": "Question requiring a brief written answer",
                    "expected_answer": "The key points that should be in a correct answer",
                    "explanation": "Detailed explanation of the correct answer"
                }},
                {{
                    "type": "short_answer",
                    "question": "Question requiring a brief written answer",
                    "expected_answer": "The key points that should be in a correct answer",
                    "explanation": "Detailed explanation of the correct answer"
                }}
            ]
        }}
    ],
    "final_exam": [
        {{
            "type": "multiple_choice or short_answer",
            "question": "Question text",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "Correct answer",
            "expected_answer": "For short answer questions",
            "explanation": "Why this is correct",
            "lesson_index": 0
        }}
    ]
}}

Requirements:
- Create 5-8 lessons that progressively build on each other
- Each lesson quiz has exactly 4 questions: 2 multiple-choice and 2 short-answer
- The final exam has exactly 10 questions covering all lessons (mix of types)
- Each final exam question should reference which lesson it covers via lesson_index
- Content should be educational, accurate, and well-structured
- Use markdown formatting in lesson content (headers, bold, code blocks where appropriate)
- For technical/coding topics, include practical code examples with explanations showing how to use each concept. Include input/output where relevant.
- For non-coding topics, include real-world scenarios and step-by-step walkthroughs
- Quiz questions should test both understanding and practical application

Return ONLY valid JSON, no markdown code fences or other text."""

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are an expert course creator. Explain concepts clearly and include practical examples showing how to use them. Balance theory with hands-on learning. Always return valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=16000,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    return json.loads(content)


def chat_with_tutor(course_topic, lesson_title, lesson_content, messages):
    system_prompt = f"""You are a helpful tutor for a course on "{course_topic}". The student is currently on a lesson titled "{lesson_title}".

Here is the lesson content they're studying:
---
{lesson_content}
---

Answer the student's questions about this lesson. Be clear, concise, and practical. If they ask how to use something, show code examples. If they ask for clarification, explain in a different way. Stay focused on the lesson topic."""

    chat_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        chat_messages.append({"role": msg["role"], "content": msg["content"]})

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=chat_messages,
        temperature=0.5,
        max_tokens=2000
    )

    return response.choices[0].message.content


def grade_short_answer(question, expected_answer, user_answer):
    if not user_answer or not user_answer.strip():
        return {"score": 0, "feedback": "No answer provided."}

    prompt = f"""Grade this student's answer to a quiz question.

Question: {question}
Expected answer: {expected_answer}
Student's answer: {user_answer}

Return a JSON object with:
{{
    "score": <0 or 1>,
    "feedback": "Brief feedback explaining why the answer is correct or incorrect"
}}

Scoring rules:
- Score 1 if the student demonstrates understanding of the key concepts, even if wording differs
- Score 0 if the answer is wrong, too vague, or misses the key points
- Be fair but not overly lenient

Return ONLY valid JSON."""

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a fair but rigorous teacher grading student answers. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=200,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    return json.loads(content)
