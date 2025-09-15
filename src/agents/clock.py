from autogen_core import Agent, DefaultTopicId, message_handler, MessageContext, RoutedAgent
from messages.messages import Message_Request, Message_Tick, MetricsReport, Message_End
import asyncio

class ClockAgent(RoutedAgent):
    def __init__(self, name, total_minutes, num_airports, num_aircraft):
        super().__init__(name)
        self.total_minutes = total_minutes
        self.metrics = []
        self.num_airports = num_airports
        self.num_aircraft = num_aircraft
        self.received_reports = 0

    @message_handler
    async def  start(self, message: Message_Request, ctx: MessageContext) -> None:
        for t in range(self.total_minutes):
            print(f"\n===== MINUTO {t} =====")
            tick_msg = Message_Tick(time=t)
            await self.publish_message(tick_msg, topic_id=DefaultTopicId())
            await asyncio.sleep(1)
            
        end_msg = Message_End()
        await self.publish_message(end_msg, topic_id=DefaultTopicId())
        

    @message_handler
    async def on_metrics_report(self, message: MetricsReport, ctx: MessageContext) -> None:
        self.metrics.append(message.data)
        self.received_reports += 1
        if self.received_reports == (self.num_airports + self.num_aircraft):
            self.print_summary()

    def print_summary(self):
        print("\n===== RESUMEN DE MÉTRICAS =====\n")
        print(f"Tiempo total simulación: {self.total_minutes} minutos")
        print(f"Número de aeropuertos: {self.num_airports}")
        print(f"Número de aviones: {self.num_aircraft}")
        print(f"Dimenes de la cuadrícula")
        print("-------------------------------\n")
        

        
        airport_metrics = [m for m in self.metrics if m and 'airport_id' in m]
        num_runways = [m.get('num_runways', 0) for m in airport_metrics]
        takeoffs = [m.get('takeoffs', 0) for m in airport_metrics]
        landings = [m.get('landings', 0) for m in airport_metrics]
        aircraft_metrics = [m for m in self.metrics if m and 'aircraft_id' in m]       

        takeoff_delays = []
        landing_delays = []
        for m in aircraft_metrics:
            takeoff_delays.extend([d['delay'] for d in m.get('takeoff_delays', [])])
            landing_delays.extend([d['delay'] for d in m.get('landing_delays', [])])

        def stats(lst):
            if not lst:
                return (None, None, None)
            return (max(lst), min(lst), sum(lst)/len(lst))

        max_r, min_r, mean_r = stats(num_runways)
        max_t, min_t, mean_t = stats(takeoffs)
        max_l, min_l, mean_l = stats(landings)
        t_max, t_min, t_avg = stats(takeoff_delays)
        l_max, l_min, l_avg = stats(landing_delays)

        print("--- Estadísticas ---")
        max_r, min_r, mean_r = stats(num_runways)
        max_t, min_t, mean_t = stats(takeoffs)
        max_l, min_l, mean_l = stats(landings)
        t_max, t_min, t_avg = stats(takeoff_delays)
        l_max, l_min, l_avg = stats(landing_delays)

        print("Máximo, mínimo y valor medio de pistas de aeropuertos:")
        print(f"  Máx: {max_r}  Mín: {min_r}  Media: {mean_r:.2f}" if max_r is not None else "  Sin datos")
        print("Máximo, mínimo y valor medio de despegues:")
        print(f"  Máx: {max_t}  Mín: {min_t}  Media: {mean_t:.2f}" if max_t is not None else "  Sin datos")
        print("Máximo, mínimo y valor medio de aterrizajes:")
        print(f"  Máx: {max_l}  Mín: {min_l}  Media: {mean_l:.2f}" if max_l is not None else "  Sin datos")
        print("Máximo, mínimo y valor medio de retrasos en despegues:")
        print(f"  Máx: {t_max}  Mín: {t_min}  Media: {t_avg:.2f}" if t_max is not None else "  Sin datos")
        print("Máximo, mínimo y valor medio de retrasos en aterrizajes:")
        print(f"  Máx: {l_max}  Mín: {l_min}  Media: {l_avg:.2f}" if l_max is not None else "  Sin datos")
        print("-------------------------------\n")

        for i, m in enumerate(self.metrics):
            if not m:
                print(f"Agente {i+1}: Sin datos de métricas.")
                continue
            print(f"Agente {i+1}:")
            for k, v in m.items():
                print(f"  {k}: {v}")
            print()

        print("-------------------------------\n")
