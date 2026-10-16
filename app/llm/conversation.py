from app.llm.state import ConversationState


class Conversation:

    def __init__(self):
        self.messages = []
        self.state = ConversationState()

    def add_user_message(self, message):
        self.messages.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": message
                    }
                ]
            }
        )

    def add_ai_message(self, message):
        self.messages.append(message)

    def add_tool_result(self, tool_name, result):
        self.messages.append(
            {
                "role": "user",
                "parts": [
                    {
                        "function_response": {
                            "name": tool_name,
                            "response": result
                        }
                    }
                ]
            }
        )

    def get_messages(self):
        return self.messages 