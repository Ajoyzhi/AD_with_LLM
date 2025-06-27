from langchain.llms import OpenAI
from langchain_deepseek import ChatDeepSeek
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from vectorStore import DrivingMemory

class LLM_Agent:
    def __init__(self, config):
        self.config = config
        # load LLM model and memory
        if self.config.llm_type == "":
            print("use gpt model")
            self.llm = OpenAI(
                model=self.config.llm_model,
                openai_api_key=self.config.llm_key,
                temperature=0,
            )
            self.memory = DrivingMemory(emb_type='openai',
                                        rule_path=self.config.rule_path,
                                        emergency_path=self.config.memory_path)
        elif self.config.llm_type == "deepseek":
            self.llm = ChatDeepSeek(
                model=self.config.llm_model, # deepseek-chat
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=self.config.llm_key,
            )
            self.memory = DrivingMemory(emb_type='huggingface',
                                        rule_path=self.config.rule_path,
                                        emergency_path=self.config.memory_path)
        else:
            # for test
            self.llm = ChatDeepSeek(
                model=self.config.llm_model,
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=self.config.llm_key,
            )
            self.memory = DrivingMemory(emb_type='',
                                        rule_path=self.config.rule_path,
                                        emergency_path=self.config.memory_path)

        # design output parser
        response_schemas = [
            ResponseSchema(name="analysis", description="analyze the driving situation."),
            ResponseSchema(name="waypoints", description="the predicted waypoints."),
            ResponseSchema(name="end_prob", description="a float number whether the driving stop.")

        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        self.format_instructions = self.output_parser.get_format_instructions()

        # design prompt
        self.message = []
        system_template = "You are a driver assistant for autonomous driving. " \
                          "The surroundings of the ego vehicle and some driving information are provided as follows."
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        self.message.append(system_message_prompt)

        human_template = "{scenario_description}"\
                         "The current instruction you receive is {instruction}. "\
                         "The things you should notice is {notice}. "\
                         "Your current speed is {velocity}, and target point is {target_point}."\
                         "Please analyze the information and generate {waypoint_number} waypoints."\
                         "Then give a float number to show stop probability whether the vehicle should stop. " \
                         "{format_instructions}"
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
        self.message.append(human_message_prompt)

    def response(self, waypoint_number: int, image_descriptions: list, drive_information: dict):
        scenario_description = f"The front camera shows {image_descriptions[0]}, " \
                               f"and the left camera shows {image_descriptions[1]}. " \
                               f"The right camera shows {image_descriptions[2]}, " \
                               f"and the rear camera shows {image_descriptions[3]}."
        # retrieve
        retrieved_template = "When the similar situations occur, the follow waypoints and actions are suggested."
        examples = self.memory.retriveMemory(scenario_description, top_k=5)
        for example in examples:
            retrieved_template = retrieved_template + "Waypoints:" + example["waypoints"] + \
                                 "; Actions:" + example["action"] + ". "
        retrieved_message_prompt = HumanMessagePromptTemplate.from_template(retrieved_template)
        self.message.append(retrieved_message_prompt)

        # generate prompt
        self.chat_prompt = ChatPromptTemplate.from_messages(self.message)
        messages = self.chat_prompt.format_messages(waypoint_number=waypoint_number,
                                                    scenario_description=scenario_description,
                                                    instruction=drive_information['text_input'][0],
                                                    notice=drive_information['notice_text'][0],
                                                    velocity=drive_information['velocity'],
                                                    target_point=drive_information['target_point'],
                                                    format_instructions=self.format_instructions)
        # llm response
        response = self.llm.invoke(messages)
        print(response.content)
        output_dict = self.output_parser.parse(response.content)  # get dictionary

        # add memory TODO
        self.memory.addMemory(sce_descrip=scenario_description,
                              analysis=output_dict['analysis'],
                              action=output_dict['action'],
                              waypoints=output_dict['waypoints'],)
        return output_dict

