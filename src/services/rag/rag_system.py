import json
import logging
from typing import List, Dict, Any
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, knowledge_base_path: str = None):
        from ...core.config import config
        if knowledge_base_path is None:
            knowledge_base_path = config.knowledge_base_dir / "knowledge_base.json"
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_base = {}
        self.load_knowledge_base()
    
    def load_knowledge_base(self):
        """Загрузить базу знаний из JSON файла"""
        try:
            with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
            logger.info(f"База знаний загружена из {self.knowledge_base_path}")
            logger.info(f"Разделы в базе знаний: {list(self.knowledge_base.keys())}")
        except FileNotFoundError:
            logger.error(f"Файл базы знаний {self.knowledge_base_path} не найден")
            self.knowledge_base = {}
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            self.knowledge_base = {}
    
    def search_knowledge(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Поиск релевантной информации в базе знаний"""
        logger.info(f"Поиск по запросу: '{query}'")
        
        if not self.knowledge_base:
            logger.warning("База знаний пуста")
            return []
        
        query_lower = query.lower()
        results = []
        
        # Улучшенное извлечение ключевых слов
        keywords = self._extract_keywords(query_lower)
        logger.info(f"Извлеченные ключевые слова: {keywords}")
        
        # Поиск в разных разделах базы знаний
        technopark_info = self.knowledge_base.get("technopark_info", {})
        
        # Специальная обработка для запросов об адресе/местоположении
        location_keywords = ['адрес', 'находится', 'расположен', 'местоположение', 'место', 'где', 'география', 'район']
        is_location_query = any(word in query_lower for word in location_keywords)
        
        # Поиск в общей информации (приоритет для запросов о местоположении)
        general_info = technopark_info.get("general", {})
        if general_info:
            # Для запросов о местоположении - всегда включаем общую информацию
            if is_location_query or self._match_content(keywords, str(general_info)):
                relevance = self._calculate_relevance(query_lower, str(general_info))
                # Увеличиваем релевантность для запросов о местоположении
                if is_location_query:
                    relevance += 0.3
                
                results.append({
                    "section": "general_info",
                    "title": "Общая информация о технопарке",
                    "content": general_info,
                    "relevance": min(1.0, relevance)
                })
                logger.info(f"Найдена общая информация, релевантность: {min(1.0, relevance)}")
        
        # Поиск в образовательных программах
        programs = technopark_info.get("educational_programs", [])
        for program in programs:
            if self._match_content(keywords, str(program)):
                relevance = self._calculate_relevance(query_lower, str(program))
                results.append({
                    "section": "educational_programs",
                    "title": f"Программа: {program.get('name', 'Неизвестная программа')}",
                    "content": program,
                    "relevance": relevance
                })
                logger.info(f"Найдена программа '{program.get('name')}', релевантность: {relevance}")
        
        # Поиск в информации о поступлении
        enrollment = technopark_info.get("enrollment", {})
        if enrollment and self._match_content(keywords, str(enrollment)):
            relevance = self._calculate_relevance(query_lower, str(enrollment))
            results.append({
                "section": "enrollment",
                "title": "Информация о поступлении",
                "content": enrollment,
                "relevance": relevance
            })
            logger.info(f"Найдена информация о поступлении, релевантность: {relevance}")
        
        # Поиск в мероприятиях
        events = technopark_info.get("events", [])
        for event in events:
            if self._match_content(keywords, str(event)):
                relevance = self._calculate_relevance(query_lower, str(event))
                results.append({
                    "section": "events",
                    "title": f"Мероприятие: {event.get('name', 'Неизвестное мероприятие')}",
                    "content": event,
                    "relevance": relevance
                })
                logger.info(f"Найдено мероприятие '{event.get('name')}', релевантность: {relevance}")
        
        # Поиск в FAQ
        faq = technopark_info.get("faq", [])
        for item in faq:
            if self._match_content(keywords, str(item)):
                relevance = self._calculate_relevance(query_lower, str(item))
                results.append({
                    "section": "faq",
                    "title": f"FAQ: {item.get('question', 'Вопрос')}",
                    "content": item,
                    "relevance": relevance
                })
                logger.info(f"Найден FAQ: '{item.get('question')}', релевантность: {relevance}")
        
        # Поиск в оборудовании
        facilities = technopark_info.get("facilities", [])
        for facility in facilities:
            if self._match_content(keywords, str(facility)):
                relevance = self._calculate_relevance(query_lower, str(facility))
                results.append({
                    "section": "facilities",
                    "title": f"Оборудование: {facility.get('name', 'Неизвестное оборудование')}",
                    "content": facility,
                    "relevance": relevance
                })
                logger.info(f"Найдено оборудование '{facility.get('name')}', релевантность: {relevance}")
        
        # Сортировка по релевантности и возврат топ результатов
        results.sort(key=lambda x: x["relevance"], reverse=True)
        logger.info(f"Найдено результатов: {len(results)}, возвращаем топ {max_results}")
        
        return results[:max_results]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Извлечь ключевые слова из запроса"""
        # Простое извлечение ключевых слов
        keywords = re.findall(r'\b\w+\b', text)
        
        # Расширенный список стоп-слов
        stop_words = {
            'как', 'что', 'где', 'когда', 'почему', 'какой', 'какая', 'какие', 'сколько',
            'и', 'или', 'но', 'а', 'в', 'на', 'по', 'для', 'с', 'от', 'до', 'за', 'под',
            'я', 'ты', 'он', 'она', 'мы', 'вы', 'они', 'это', 'то', 'тот', 'та', 'те',
            'мне', 'мной', 'меня', 'тебя', 'его', 'её', 'нас', 'вас', 'их', 'им', 'ему',
            'есть', 'быть', 'был', 'была', 'было', 'были', 'буду', 'будет', 'будут',
            'можно', 'нужно', 'надо', 'хочу', 'хочет', 'хотим', 'хотите', 'хотят',
            'скажите', 'расскажите', 'объясните', 'помогите', 'дайте', 'покажите'
        }
        
        # Добавляем синонимы и ключевые слова для лучшего поиска
        keyword_mapping = {
            'программа': ['курс', 'занятие', 'обучение', 'изучение', 'направление', 'специальность'],
            'робототехника': ['робот', 'роботы', 'робототехнический', 'роботостроение'],
            'программирование': ['код', 'кодирование', 'разработка', 'python', 'javascript', 'языки', 'язык'],
            'поступление': ['поступить', 'записаться', 'запись', 'регистрация', 'документы', 'зачисление'],
            'стоимость': ['цена', 'оплата', 'платить', 'деньги', 'рублей', 'стоит', 'затраты', 'плата'],
            'расписание': ['график', 'время', 'часы', 'когда', 'занятия'],
            'возраст': ['лет', 'года', 'детям', 'ребенок', 'школьник', 'подросток'],
            'мероприятие': ['событие', 'хакатон', 'выставка', 'день', 'конкурс', 'соревнование'],
            'оборудование': ['лаборатория', 'компьютер', 'принтер', '3d', 'техника', 'устройство'],
            'контакты': ['телефон', 'адрес', 'связаться', 'написать', 'найти', 'обратиться'],
            'местоположение': ['адрес', 'находится', 'расположен', 'где', 'место', 'локация', 'география', 'район'],
            'технопарк': ['центр', 'учреждение', 'организация', 'место', 'школа'],
            'общая': ['информация', 'данные', 'сведения', 'описание', 'о', 'про']
        }
        
        # Специальные фразы для поиска
        text_lower = text.lower()
        special_phrases = {
            'адрес': ['адрес', 'находится', 'расположен', 'местоположение', 'место', 'где'],
            'контакты': ['контакт', 'телефон', 'связь', 'написать'],
            'время_работы': ['работа', 'время', 'часы', 'режим', 'график'],
            'общая_информация': ['информация', 'данные', 'сведения', 'описание', 'про', 'о']
        }
        
        # Проверяем специальные фразы
        detected_phrases = []
        for phrase_type, phrase_keywords in special_phrases.items():
            if any(phrase_word in text_lower for phrase_word in phrase_keywords):
                detected_phrases.append(phrase_type)
        
        # Базовые ключевые слова
        filtered_keywords = [word for word in keywords if word not in stop_words and len(word) > 2]
        
        # Добавляем обнаруженные фразы
        filtered_keywords.extend(detected_phrases)
        
        # Добавляем синонимы
        extended_keywords = filtered_keywords.copy()
        for keyword in filtered_keywords:
            for main_word, synonyms in keyword_mapping.items():
                if keyword in synonyms:
                    extended_keywords.append(main_word)
                elif keyword == main_word:
                    extended_keywords.extend(synonyms)
        
        logger.info(f"Исходный текст: '{text}'")
        logger.info(f"Базовые ключевые слова: {filtered_keywords}")
        logger.info(f"Расширенные ключевые слова: {list(set(extended_keywords))}")
        
        return list(set(extended_keywords))  # Убираем дубликаты
    
    def _match_content(self, keywords: List[str], content: str) -> bool:
        """Проверить соответствие контента ключевым словам"""
        if not keywords:
            return False
        
        content_lower = content.lower()
        matches = sum(1 for keyword in keywords if keyword in content_lower)
        
        # Возвращаем True если найдено хотя бы одно ключевое слово
        return matches > 0
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """Вычислить релевантность контента для запроса"""
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Базовая релевантность по строковому сходству
        base_relevance = SequenceMatcher(None, query_lower, content_lower).ratio()
        
        # Дополнительные очки за точные совпадения ключевых слов
        keywords = self._extract_keywords(query_lower)
        keyword_matches = sum(1 for keyword in keywords if keyword in content_lower)
        keyword_bonus = (keyword_matches / len(keywords)) * 0.5 if keywords else 0
        
        return min(1.0, base_relevance + keyword_bonus)
    
    def get_context_for_query(self, query: str) -> str:
        """Получить контекст для запроса в формате для DeepSeek API"""
        logger.info(f"Получение контекста для запроса: '{query}'")
        
        results = self.search_knowledge(query)
        
        if not results:
            logger.warning("Результаты поиска не найдены")
            return "Информация по данному запросу не найдена в базе знаний технопарка."
        
        context_parts = []
        for i, result in enumerate(results):
            logger.info(f"Обработка результата {i+1}: {result['title']}")
            content = result["content"]
            
            if result["section"] == "general_info":
                context_parts.append(self._format_general_info(content))
            elif result["section"] == "educational_programs":
                context_parts.append(self._format_program_info(content))
            elif result["section"] == "enrollment":
                context_parts.append(self._format_enrollment_info(content))
            elif result["section"] == "events":
                context_parts.append(self._format_event_info(content))
            elif result["section"] == "faq":
                context_parts.append(self._format_faq_info(content))
            elif result["section"] == "facilities":
                context_parts.append(self._format_facility_info(content))
        
        final_context = "\n\n".join(context_parts)
        logger.info(f"Сформирован контекст длиной {len(final_context)} символов")
        
        return final_context
    
    def _format_general_info(self, info: Dict) -> str:
        """Форматировать общую информацию"""
        text = f"Информация о {info.get('name', 'технопарке')}:\n"
        text += f"Описание: {info.get('description', '')}\n"
        text += f"Возрастные группы: {', '.join(info.get('age_groups', []))}\n"
        text += f"Режим работы: {info.get('working_hours', '')}\n"
        
        contacts = info.get('contacts', {})
        if contacts:
            text += "Контакты:\n"
            text += f"  Телефон: {contacts.get('phone', '')}\n"
            text += f"  Email: {contacts.get('email', '')}\n"
            text += f"  Адрес: {contacts.get('address', '')}\n"
        
        return text
    
    def _format_program_info(self, program: Dict) -> str:
        """Форматировать информацию о программе"""
        text = f"Программа '{program.get('name', 'Неизвестная')}':\n"
        text += f"Описание: {program.get('description', '')}\n"
        text += f"Возрастные группы: {', '.join(program.get('age_groups', []))}\n"
        text += f"Продолжительность: {program.get('duration', '')}\n"
        text += f"Расписание: {program.get('schedule', '')}\n"
        text += f"Стоимость: {program.get('price', '')}\n"
        
        if 'technologies' in program:
            text += f"Технологии: {', '.join(program['technologies'])}\n"
        
        if 'skills' in program:
            text += f"Навыки: {', '.join(program['skills'])}\n"
        
        if 'enrollment_requirements' in program:
            text += f"Требования: {program['enrollment_requirements']}\n"
        
        return text
    
    def _format_enrollment_info(self, enrollment: Dict) -> str:
        """Форматировать информацию о поступлении"""
        text = "Информация о поступлении:\n"
        
        if 'required_documents' in enrollment:
            text += "Необходимые документы:\n"
            for doc in enrollment['required_documents']:
                text += f"  - {doc}\n"
        
        if 'enrollment_process' in enrollment:
            text += "Процесс поступления:\n"
            for step in enrollment['enrollment_process']:
                text += f"  - {step}\n"
        
        if 'payment_options' in enrollment:
            text += "Варианты оплаты:\n"
            for option in enrollment['payment_options']:
                text += f"  - {option}\n"
        
        if 'discounts' in enrollment:
            text += "Скидки:\n"
            for discount in enrollment['discounts']:
                text += f"  - {discount['type']}: {discount['amount']}\n"
        
        return text
    
    def _format_event_info(self, event: Dict) -> str:
        """Форматировать информацию о мероприятии"""
        text = f"Мероприятие '{event.get('name', 'Неизвестное')}':\n"
        text += f"Описание: {event.get('description', '')}\n"
        
        if 'dates' in event:
            text += f"Даты: {', '.join(event['dates'])}\n"
        
        if 'time' in event:
            text += f"Время: {event['time']}\n"
        
        if 'free' in event and event['free']:
            text += "Участие бесплатное\n"
        
        if 'prizes' in event:
            text += f"Призы: {event['prizes']}\n"
        
        return text
    
    def _format_faq_info(self, faq: Dict) -> str:
        """Форматировать информацию из FAQ"""
        return f"Вопрос: {faq.get('question', '')}\nОтвет: {faq.get('answer', '')}"
    
    def _format_facility_info(self, facility: Dict) -> str:
        """Форматировать информацию об оборудовании"""
        text = f"Помещение '{facility.get('name', 'Неизвестное')}':\n"
        
        if 'equipment' in facility:
            text += f"Оборудование: {', '.join(facility['equipment'])}\n"
        
        if 'capacity' in facility:
            text += f"Вместимость: {facility['capacity']}\n"
        
        return text

# Создаем глобальный экземпляр RAG системы
rag_system = RAGSystem() 