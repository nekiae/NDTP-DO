"""
Клиент для работы с DeepSeek API
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import config

logger = logging.getLogger(__name__)


class DeepSeekAPI:
    """
    Клиент для взаимодействия с DeepSeek API
    
    Поддерживает обычные и стриминговые запросы с retry логикой
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.deepseek_api_key
        self.api_url = config.deepseek_api_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Семафор для ограничения одновременных запросов
        self.semaphore = asyncio.Semaphore(config.llm_concurrency_limit)
        
        logger.info("🧠 DeepSeek API клиент инициализирован")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60), 
        stop=stop_after_attempt(5)
    )
    async def _make_request(self, payload: Dict) -> Optional[Dict]:
        """
        Защищённый HTTP запрос с retry логикой
        
        Args:
            payload: Данные запроса
            
        Returns:
            Ответ API или None в случае ошибки
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url, 
                headers=self.headers, 
                json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(f"⚠️ Rate limit (429), retry after {retry_after}s")
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=429,
                        message=f"Rate limit exceeded, retry after {retry_after}s",
                    )
                else:
                    logger.error(f"❌ DeepSeek API error: {response.status}")
                    response.raise_for_status()

    async def get_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        model: str = "deepseek-chat"
    ) -> Optional[str]:
        """
        Получить обычный ответ от DeepSeek API
        
        Args:
            messages: Список сообщений для API
            temperature: Температура для генерации (0.0-1.0)
            model: Модель для использования
            
        Returns:
            Текст ответа или None в случае ошибки
        """
        try:
            async with self.semaphore:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }

                result = await self._make_request(payload)
                if result and "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка в DeepSeek API запросе: {e}")
            return None

    async def get_streaming_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        model: str = "deepseek-chat"
    ) -> AsyncGenerator[Optional[str], None]:
        """
        Генератор для стриминговых ответов от DeepSeek API
        
        Args:
            messages: Список сообщений для API
            temperature: Температура для генерации (0.0-1.0)
            model: Модель для использования
            
        Yields:
            Части ответа по мере их генерации
        """
        try:
            async with self.semaphore:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                }

                # Повторяем попытки при ошибках
                for attempt in range(3):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                self.api_url, 
                                headers=self.headers, 
                                json=payload
                            ) as response:
                                if response.status == 429:
                                    retry_after = int(
                                        response.headers.get("Retry-After", "60")
                                    )
                                    logger.warning(
                                        f"⚠️ Rate limit при стриминге, ждём {retry_after}s"
                                    )
                                    await asyncio.sleep(retry_after)
                                    continue

                                if response.status == 200:
                                    async for line in response.content:
                                        line = line.decode("utf-8").strip()
                                        if line.startswith("data: "):
                                            line = line[6:]  # Убираем "data: "
                                            if line == "[DONE]":
                                                break
                                            try:
                                                data = json.loads(line)
                                                if (
                                                    "choices" in data
                                                    and len(data["choices"]) > 0
                                                ):
                                                    delta = data["choices"][0].get("delta", {})
                                                    if "content" in delta:
                                                        yield delta["content"]
                                            except json.JSONDecodeError:
                                                continue
                                    return
                                else:
                                    logger.error(
                                        f"❌ DeepSeek streaming error: {response.status}"
                                    )
                                    if attempt < 2:
                                        await asyncio.sleep(2**attempt)
                                        continue
                                    else:
                                        yield None
                                        return

                    except Exception as e:
                        logger.error(f"❌ Streaming attempt {attempt + 1} failed: {e}")
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        else:
                            yield None
                            return

        except Exception as e:
            logger.error(f"❌ Ошибка в DeepSeek streaming API: {e}")
            yield None

    async def test_connection(self) -> bool:
        """
        Тестирование соединения с API
        
        Returns:
            True если соединение работает
        """
        try:
            test_messages = [
                {"role": "user", "content": "Привет"}
            ]
            
            result = await self.get_completion(test_messages, temperature=0.1)
            
            if result:
                logger.info("✅ DeepSeek API соединение работает")
                return True
            else:
                logger.error("❌ DeepSeek API вернул пустой результат")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования DeepSeek API: {e}")
            return False

    def get_usage_stats(self) -> Dict[str, any]:
        """
        Получить статистику использования API
        
        Returns:
            Словарь со статистикой
        """
        # В будущем можно добавить трекинг использования
        return {
            "api_url": self.api_url,
            "concurrency_limit": config.llm_concurrency_limit,
            "has_api_key": bool(self.api_key),
        }


# Глобальный экземпляр клиента
deepseek_client = DeepSeekAPI()
