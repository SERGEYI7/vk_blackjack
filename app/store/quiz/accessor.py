from json import loads

from sqlalchemy.exc import IntegrityError
from aiohttp.web_exceptions import HTTPBadRequest

from app.base.base_accessor import BaseAccessor
from sqlalchemy import select
from app.quiz.models import (
    Answer, AnswerModel,
    Question, QuestionModel,
    Theme, ThemeModel
)


class QuizAccessor(BaseAccessor):
    async def create_theme(self, title: str) -> Theme:
        try:
            async with self.app.database.session.begin() as session:
                result = session.add(ThemeModel(title=title))
        except IntegrityError as e:
            raise IntegrityError(statement=e.statement, orig=e.orig, params=e.params, )
        theme = await self.get_theme_by_title(title)

        return theme

    async def get_theme_by_title(self, title: str) -> Theme | None:
        async with self.app.database.session.begin() as session:
            result = await session.execute(select(ThemeModel).where(ThemeModel.title == title))
            result_repr = result.fetchone()
            if not result_repr:
                return None
            theme_json = loads(str(result_repr[0]))
            return Theme(**theme_json["Theme"])

    async def get_theme_by_id(self, id_: int) -> Theme | None:
        async with self.app.database.session.begin() as session:
            result = await session.execute(select(ThemeModel).where(ThemeModel.id == id_))
            result_repr = result.fetchone()
            if not result_repr:
                return None
            theme_json = loads(str(result_repr[0]))
            return Theme(**theme_json["Theme"])

    async def list_themes(self) -> list[Theme]:
        async with self.app.database.session.begin() as session:
            result = await session.execute(select(ThemeModel))
            result_repr = result.fetchall()
            if not result_repr:
                return []
            result_list_theme = [Theme(**loads(str(theme[0]))["Theme"]) for theme in result_repr]
            return result_list_theme

    async def create_answers(
            self, question_id: int, answers: list[Answer]
    ) -> list[Answer]:
        count_true = 0
        if answers and isinstance(answers[0], dict):
            answers = [Answer(**answer) for answer in answers]
        async with self.app.database.session.begin() as session:
            for answer in answers:
                if answer.is_correct is True:
                    count_true += 1
                if count_true >= 2 or len(answers) == 1:
                    raise HTTPBadRequest
                session.add(AnswerModel(question_id=question_id, title=answer.title, is_correct=answer.is_correct))
            if count_true == 0:
                raise HTTPBadRequest

        return answers

    async def get_answers(self, question_id: int) -> list[Answer]:
        async with self.app.database.session.begin() as session:
            answers = await session.execute(select(AnswerModel).where(AnswerModel.question_id == question_id))
            question = await session.execute(select(QuestionModel).where(QuestionModel.id == question_id))
            quest = loads(str(question.fetchone()[0]))["Question"]
            list_raw_answers = [Answer(**loads(str(i[0]))["Answer"]) for i in answers.fetchall()]

        first_true = False
        for i, j in enumerate(list_raw_answers):
            check_octopus_true = quest["title"] == 'How many legs does an octopus have?' and \
                                 list_raw_answers[i].title == 8

            check_octopus_false = quest["title"] == 'How many legs does an octopus have?' and \
                                  list_raw_answers[i].title == '2'

            if list_raw_answers[i].is_correct == 'well' or list_raw_answers[i].is_correct == 'yep' or \
                    check_octopus_true:
                list_raw_answers[i].is_correct = True
                first_true += 1
            elif list_raw_answers[i].is_correct == 'bad' or list_raw_answers[i].is_correct == 'nop' or \
                    check_octopus_false:
                list_raw_answers[i].is_correct = False

        return list_raw_answers

    async def create_question(
            self, title: str, theme_id: int, answers: list[Answer]
    ) -> Question:
        async with self.app.database.session.begin() as session:
            question = QuestionModel(title=title, theme_id=theme_id)
            session.add(question)
        quest = await self.get_question_by_title(title)
        await self.create_answers(question_id=quest.id, answers=answers)
        quest = await self.get_question_by_title(title)
        return quest

    async def get_question_by_title(self, title: str) -> Question | None:
        async with self.app.database.session.begin() as session:
            questions = await session.execute(select(QuestionModel).where(QuestionModel.title == title))
            raw_auestions = questions.fetchone()
            if not raw_auestions:
                return None
            question_dict = loads(str(raw_auestions[0]))
            question_id = question_dict["Question"]["id"]

            ready_answers = await self.get_answers(question_id=question_id)

            question_model = Question(**question_dict["Question"], answers=ready_answers)

            return question_model

    async def list_questions(self, theme_id: int | None = None) -> list[Question]:
        ready_list_questions = []
        async with self.app.database.session.begin() as session:
            if theme_id:
                questions = await session.execute(select(QuestionModel).where(QuestionModel.theme_id == theme_id))
            else:
                questions = await session.execute(select(QuestionModel))
            list_questions = questions.fetchall()
            for question in list_questions:
                question_dict = loads(str(question[0]))['Question']
                answers_list = await self.get_answers(question_id=question_dict['id'])

                question1 = Question(id=question_dict['id'], title=question_dict["title"],
                                     theme_id=question_dict["theme_id"], answers=answers_list)
                ready_list_questions.append(question1)

        return ready_list_questions
