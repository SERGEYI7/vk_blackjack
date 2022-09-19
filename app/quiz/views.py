from aiohttp.web_exceptions import HTTPNotFound
from aiohttp_apispec import querystring_schema, request_schema, response_schema
from app.quiz.schemes import (
    ListQuestionSchema,
    QuestionSchema,
    ThemeIdSchema,
    ThemeListSchema,
    ThemeSchema,
)
from app.web.app import View
from app.web.mixins import AuthRequiredMixin
from app.web.utils import json_response


class ThemeAddView(AuthRequiredMixin, View):
    @request_schema(ThemeSchema)
    @response_schema(ThemeSchema)
    async def post(self):
        title = self.data.get("title")
        theme = await self.store.quizzes.create_theme(title)
        return json_response(data=ThemeSchema().dump(theme))


class ThemeListView(AuthRequiredMixin, View):
    @response_schema(ThemeListSchema)
    async def get(self):
        themes = await self.store.quizzes.list_themes()
        print(themes)
        model_themes = [ThemeSchema().dump(theme) for theme in themes]
        return json_response(data={"themes": model_themes})


class QuestionAddView(AuthRequiredMixin, View):
    @request_schema(QuestionSchema)
    @response_schema(QuestionSchema)
    async def post(self):
        request = await self.request.json()
        title = request["title"]
        theme_id = request["theme_id"]
        answers = request["answers"]
        if not await self.store.quizzes.get_theme_by_id(theme_id):
            raise HTTPNotFound
        result = await self.store.quizzes.create_question(title, theme_id, answers)
        model_question = QuestionSchema().dump(result)
        return json_response(data=model_question)


class QuestionListView(AuthRequiredMixin, View):
    @querystring_schema(ThemeIdSchema)
    @response_schema(ListQuestionSchema)
    async def get(self):
        questions = await self.store.quizzes.list_questions()
        ready = [QuestionSchema().dump(question) for question in questions]
        return json_response(data={"questions": ready})
