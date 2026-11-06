"""Static content: daily questions, Guess-the-Band samples, cities, schools.

All questions and sample answers are original texts written for this prototype
(IELTS Speaking Part 2 style), not official IELTS materials.
"""

CITIES = ["Almaty", "Astana", "Shymkent", "Oral", "Atyrau", "Aktobe", "Karaganda", "Other"]

SCHOOLS = [
    "NIS",
    "BIL",
    "RFMSH",
    "Lyceum No.165",
    "KTL",
    "Gymnasium",
    "University",
]

TARGETS = ["5.5", "6.0", "6.5", "7.0", "7.5", "8.0+"]

# IELTS Speaking Part 2 style cue cards (original wording)
QUESTIONS = [
    ("Describe a skill you learned outside school.",
     ["what the skill is", "how you learned it", "how long it took", "and explain why it is useful to you"]),
    ("Describe a place in Kazakhstan you would recommend to a foreign visitor.",
     ["where it is", "how you know about it", "what people can do there", "and explain why you recommend it"]),
    ("Describe a person who inspired you to study harder.",
     ["who this person is", "how you know them", "what they did", "and explain how they changed your attitude"]),
    ("Describe an app you use every day.",
     ["what it is", "when you started using it", "what you use it for", "and explain why it matters to you"]),
    ("Describe a time you had to make a difficult decision.",
     ["what the decision was", "when it happened", "what options you had", "and explain how you feel about it now"]),
    ("Describe a goal you want to achieve in the next five years.",
     ["what the goal is", "why you chose it", "what you are doing to reach it", "and explain how you will feel if you achieve it"]),
    ("Describe a traditional celebration in your country.",
     ["what it is", "when it happens", "what people do", "and explain why it is important"]),
    ("Describe a book, film or series that changed your opinion about something.",
     ["what it was", "when you saw or read it", "what it was about", "and explain how your opinion changed"]),
    ("Describe a time you worked in a team to achieve something.",
     ["what the task was", "who was in the team", "what your role was", "and explain what you learned"]),
    ("Describe a city abroad where you would like to study.",
     ["which city it is", "how you learned about it", "what you would study there", "and explain why it attracts you"]),
    ("Describe a piece of technology you could not live without.",
     ["what it is", "how long you have had it", "how often you use it", "and explain why it is so important to you"]),
    ("Describe a teacher who influenced you.",
     ["who the teacher was", "what subject they taught", "what they were like", "and explain how they influenced you"]),
    ("Describe a time you helped someone.",
     ["who you helped", "what the situation was", "how you helped", "and explain how you felt afterwards"]),
    ("Describe a sport or hobby you really enjoy.",
     ["what it is", "when you started", "how often you do it", "and explain why you enjoy it"]),
]

# "Guess the Band" mini-game. Illustrative answers written by the Band Battle team.
# Target bands are our own calibration for the demo, not official IELTS ratings.
GUESS_SAMPLES = [
    {
        "question": "Describe a place in Kazakhstan you would recommend to a foreign visitor.",
        "speaker": "Student A, 10th grade",
        "text": (
            "Okay, so I want to talk about Shymbulak. It is very beautiful place, there is mountains "
            "and, um, a lot of snow. I go there with my family every winter. We are skiing and also "
            "we eat in cafe. I am agree that it is expensive, but it is very good for relax. I think "
            "foreign people will like it because it is near the city and not so difficult to go."
        ),
        "band": "5.5",
        "why": (
            "Ideas are clear, but grammar errors repeat ('there is mountains', 'I am agree', "
            "'good for relax') and vocabulary stays basic ('very beautiful', 'very good')."
        ),
    },
    {
        "question": "Describe a place in Kazakhstan you would recommend to a foreign visitor.",
        "speaker": "Student B, 1st-year university",
        "text": (
            "I'd like to talk about Charyn Canyon, which is about three hours from Almaty. I went there "
            "last summer with my classmates, and honestly it was one of the most impressive places I've "
            "ever seen. The rocks have this red and orange colour, and when the sun goes down it looks "
            "really unreal. The only problem is the road, it's quite long and a bit tiring, but I think "
            "it's definitely worth it, especially for tourists who want to see something different."
        ),
        "band": "6.5",
        "why": (
            "Fluent and well linked, with some good collocations ('most impressive places I've ever seen'). "
            "Range is still fairly safe and a few phrases are vague ('really unreal', 'something different')."
        ),
    },
    {
        "question": "Describe a place in Kazakhstan you would recommend to a foreign visitor.",
        "speaker": "Student C, 11th grade",
        "text": (
            "The place I'd recommend without hesitation is Turkistan. What struck me most wasn't just the "
            "mausoleum of Khoja Ahmed Yasawi, although that's breathtaking, it was how the whole city seems "
            "to bridge the past and the present. Walking through the old part of town, you get a real sense "
            "of how central it was to the Silk Road. It appeals to anyone who's curious about history, but "
            "it's also surprisingly lively in the evenings, which genuinely caught me off guard."
        ),
        "band": "7.5",
        "why": (
            "Complex structures used naturally ('What struck me most wasn't just...'), precise idiomatic "
            "language ('caught me off guard', 'bridge the past and the present') and almost no errors."
        ),
    },
]

GUESS_OPTIONS = ["5.5", "6.5", "7.5"]
