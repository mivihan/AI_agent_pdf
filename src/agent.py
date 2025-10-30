"""
Агентная логика на базе GigaChat и LangChain
"""
import os
import json
import re
from typing import Any
from dotenv import load_dotenv
from langchain_community.chat_models.gigachat import GigaChat
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

from src.settings import GIGACHAT_MODEL, GIGACHAT_VERIFY_SSL, LLM_EXTRACT_PROMPT_TEMPLATE

load_dotenv()


def create_gigachat_llm(model: str = GIGACHAT_MODEL, **kwargs) -> GigaChat:
    '''Инициализация GigaChat LLM.'''
    api_key = os.getenv("GIGACHAT_API_KEY")
    if not api_key:
        raise ValueError("GIGACHAT_API_KEY не найден в .env файле")
    
    return GigaChat(
        credentials=api_key,
        model=model,
        verify_ssl_certs=GIGACHAT_VERIFY_SSL,
        timeout=120,
        temperature=0.0,
        max_tokens=1024,
        **kwargs
    )


def extract_code_with_llm(text: str, llm: GigaChat | None = None) -> dict[str, Any]:
    '''
    LLM-экстрактор кода контейнера с защитой от галлюцинаций.
    Проверяет, что код действительно есть в тексте.
    '''
    if llm is None:
        llm = create_gigachat_llm()
    
    try:
        prompt = LLM_EXTRACT_PROMPT_TEMPLATE.format(text=text[:2000])
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        json_match = re.search(r'\{[^}]+\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            code = result.get("code", "").strip()
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "LLM extraction")
            
            if code:
                from src.settings import VALIDATION_PATTERN
                normalized = code.replace(" ", "").replace("-", "").replace("_", "").upper()
                
                if not VALIDATION_PATTERN.match(normalized):
                    return {"code": "", "confidence": 0.0, "reason": f"LLM вернул невалидный формат: {code}"}
                
                text_upper = text.upper()
                code_letters = normalized[:4]
                code_digits = normalized[4:]
                
                found_in_text = False
                if normalized in text_upper:
                    found_in_text = True
                elif code_letters in text_upper and code_digits in text_upper:
                    dist = abs(text_upper.find(code_letters) - text_upper.find(code_digits))
                    if dist < 20:
                        found_in_text = True
                
                if not found_in_text:
                    return {
                        "code": "",
                        "confidence": 0.0,
                        "reason": f"LLM галлюцинация: код '{normalized}' не найден в тексте документа"
                    }
                
                return {
                    "code": normalized,
                    "confidence": min(confidence, 0.95),
                    "reason": f"LLM: {reason} (проверено в тексте)"
                }
            
            return {"code": "", "confidence": 0.0, "reason": "LLM не нашёл валидный код"}
        
        return {"code": "", "confidence": 0.0, "reason": "Некорректный формат ответа LLM"}
    
    except Exception as e:
        return {"code": "", "confidence": 0.0, "reason": f"Ошибка LLM: {str(e)}"}


def create_agent_executor(tools: list, max_iterations: int = 15, verbose: bool = True) -> AgentExecutor:
    '''
    Создание ReAct агента для обработки PDF.
    
    Агент последовательно обрабатывает каждый PDF:
    1. read_pdf_text - читает текст
    2. regex_extract_code - ищет код regex
    3. Если confidence < 0.8 - анализирует текст сам
    4. normalize_code - нормализует код
    5. safe_rename - переименовывает файл
    6. log_result - пишет в лог
    '''
    llm = create_gigachat_llm()
    
    agent_prompt = PromptTemplate.from_template("""Ты - агент для обработки PDF. Извлекаешь коды контейнеров (формат: 4 БУКВЫ + 7 ЦИФР, пример ABCD1234567).

ИНСТРУМЕНТЫ:
{tools}

ФОРМАТ РАБОТЫ:
Question: [задача]
Thought: [что делать]
Action: [инструмент из {tool_names}]
Action Input: [параметры]
Observation: [результат]
... (повторяй цикл)
Thought: Задача выполнена
Final Answer: [краткий итог]

АЛГОРИТМ:
1. read_pdf_text - читай PDF
2. regex_extract_code - ищи код
3. Если confidence < 0.8 - анализируй текст сам и найди код AAAA1234567
4. normalize_code - нормализуй
5. safe_rename - переименуй
6. log_result - запиши в лог

ПРАВИЛА:
- Обрабатывай файлы ПОСЛЕДОВАТЕЛЬНО
- НЕ генерируй отчёты в Thought - только краткие рассуждения
- Если код не найден - НЕ переименовывай, лог с reason=NOT_FOUND
- После log_result переходи к следующему файлу
- Final Answer ТОЛЬКО в конце всех файлов, максимум 2 предложения

Question: {input}

{agent_scratchpad}""")
    
    agent = create_react_agent(llm=llm, tools=tools, prompt=agent_prompt)
    
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        max_iterations=max_iterations,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )