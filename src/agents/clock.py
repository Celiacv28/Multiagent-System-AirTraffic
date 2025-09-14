from autogen_core import Agent, DefaultTopicId, message_handler, MessageContext, RoutedAgent
from messages.messages import Message_Request, Message_Tick, MetricsReport, Message_End
import asyncio

class ClockAgent(RoutedAgent):
    def __init__(self, name, total_minutes):
        super().__init__(name)
        self.total_minutes = total_minutes

    @message_handler
    async def  start(self, message: Message_Request, ctx: MessageContext) -> None:
        for t in range(self.total_minutes):
            print(f"\n===== MINUTO {t} =====")
            tick_msg = Message_Tick(time=t)
            await self.publish_message(tick_msg, topic_id=DefaultTopicId())
            await asyncio.sleep(5)
            
        end_msg = Message_End()
        await self.publish_message(end_msg, topic_id=DefaultTopicId())
        self.print_summary()

    @message_handler
    async def on_metrics_report(self, message: MetricsReport, ctx: MessageContext) -> None:
        self.metrics.append(message.data)

    def print_summary(self):
        print("Resumen de métricas:", self.metrics)

