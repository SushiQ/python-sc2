from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer
import random 
from sc2.position import Point2
from loguru import logger
from threebase_voidray import ThreebaseVoidrayBot
from cannon_rush import CannonRushBot
from g16 import StalkerCheeseBot

class Brotoss(BotAI):
    scouting_workers = []
    first_scout = True
    def __init__(self):
        super().__init__()
        self.scouting_workers = []
        self.first_scout = True
        self.scout_harassment_target = None
        self.strategy = "StalkerPush" #VoidrayRush/Stalkerpush/Immortals/DarkTemplar/Tempest
        self.STP_complete = False #Check if the stalkers are currently at full strength and harrassing
        self.firstWave = True # The first 2 stalkers will instantly attack
        self.desiredStalkerCount = 9
                
    # pylint: disable=R0912
    async def on_step(self, iteration):     
        target_base_count = 3
        target_stargate_count = 3

        if iteration == 0:
            await self.chat_send("(glhf)")
        if not self.townhalls.ready:
            # Attack with all workers if we don't have any nexuses left, attack-move on enemy spawn (doesn't work on 4 player map) so that probes auto attack on the way
            for worker in self.workers:
                worker.attack(self.enemy_start_locations[0])
            return
        nexus = self.townhalls.ready.random
        #Chronoboost warpgate if possible
        if(len(self.structures(UnitTypeId.GATEWAY).ready)>=1):
            gateway = self.structures(UnitTypeId.GATEWAY).ready.random
            if not gateway.is_idle and not gateway.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                nexuses = self.structures(UnitTypeId.NEXUS)
                abilities = await self.get_available_abilities(nexuses)
                for loop_nexus, abilities_nexus in zip(nexuses, abilities):
                    if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities_nexus:
                        loop_nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, gateway)
                        break
        # If this random nexus is not idle and has not chrono buff, chrono it with one of the nexuses we have
        if not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            nexuses = self.structures(UnitTypeId.NEXUS)
            abilities = await self.get_available_abilities(nexuses)
            for loop_nexus, abilities_nexus in zip(nexuses, abilities):
                if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities_nexus:
                    loop_nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)
                    break

        # Distribute workers in gas and across bases
        await self.distribute_workers()

        # If we are low on supply, build pylon
        if (
            self.supply_left < 2 and self.already_pending(UnitTypeId.PYLON) == 0
            or self.supply_used > 25 and self.supply_left < 4 and self.already_pending(UnitTypeId.PYLON) < 2
        ):
            # Always check if you can afford something before you build it
            if self.can_afford(UnitTypeId.PYLON):
                await self.build(UnitTypeId.PYLON, near=nexus)

        # Train probe on nexuses that are undersaturated (avoiding distribute workers functions)
        # if nexus.assigned_harvesters < nexus.ideal_harvesters and nexus.is_idle:
        if self.supply_workers + self.already_pending(UnitTypeId.PROBE) < self.townhalls.amount * 23 and nexus.is_idle:
            if self.can_afford(UnitTypeId.PROBE):
                nexus.train(UnitTypeId.PROBE)

        #Are three nexuses necessary? or should the third be considered later
        # If we have less than 3 nexuses and none pending yet, expand
        if self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) < 3 :
            if self.can_afford(UnitTypeId.NEXUS):
                await self.expand_now()

        if(self.strategy == "StalkerPush"):
            #get a defensive zealot out against possible cannon rushes
            if(self.firstWave):
                for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                    if self.can_afford(UnitTypeId.ZEALOT) and not len(self.units(UnitTypeId.ZEALOT))>4 and not self.units(UnitTypeId.ZEALOT).idle:
                        sg.train(UnitTypeId.ZEALOT)

                for zealot in self.units(UnitTypeId.ZEALOT):
                    zealot.attack(self.main_base_ramp.top_center)
            #Pylon -> Gateway -> Gateway
            await self.buildorder3Warpgate()
            #gets 6 stalkers ready
            await self.STPRecruitment()
            await self.STP()
            await self.kite()
            #await self.groupUp()
            if(self.STP_complete):
                await self.VRRstargateConstruction(target_base_count,target_stargate_count)
                #builds voidrays only if 3 nexuses are ready
                await self.VRRvoidrayRecruitment()
                await self.VRR()

        elif(self.strategy == "VoidrayRush"):
            #Pylon -> Gateway -> CyberneticsCore
            await self.buildorderCybernetics()
            #Builds 3 stargates for the voidRayRush - requires warpgate,cyberneticscore and gas
            await self.VRRstargateConstruction(target_base_count,target_stargate_count)
            #builds voidrays only if 3 nexuses are ready
            await self.VRRvoidrayRecruitment()
            await self.VRR()
        #if self.minerals > 1000 and (self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS)) < 4:
        #    if self.can_afford(UnitTypeId.NEXUS):
        #        await self.expand_now()
        if not (
            (self.units.owned or self.can_afford(UnitTypeId.PROBE))
            and self.townhalls.ready
        ):
            # Surrender when there are no nexuses left or we have no units left
            # and can't afford a worker
            await self.client.leave()
            return

    #strategy functions
    async def VRRstargateConstruction(self,target_base_count,target_stargate_count):
        #Builds 3 stargates for the voidRayRush - requires warpgate,cyberneticscore and gas
        # If we have less than 3  but at least 3 nexuses, build stargate
        if self.structures(UnitTypeId.PYLON).ready and self.structures(UnitTypeId.CYBERNETICSCORE).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if (
                self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) >= target_base_count
                and self.structures(UnitTypeId.STARGATE).ready.amount + self.already_pending(UnitTypeId.STARGATE) <
                target_stargate_count
            ):
                if self.can_afford(UnitTypeId.STARGATE):
                    await self.build(UnitTypeId.STARGATE, near=pylon)
    async def VRRvoidrayRecruitment(self):
        #builds voidrays only if 3 nexuses are ready
        # Save up for expansions, loop over idle completed stargates and queue void ray if we can afford
        if self.townhalls.amount >= 3:
            for sg in self.structures(UnitTypeId.STARGATE).ready.idle:
                if self.can_afford(UnitTypeId.VOIDRAY):
                    sg.train(UnitTypeId.VOIDRAY)
    
    async def buildorderCybernetics(self):
        #Basic build-order till cybernetics core
        # Once we have a pylon completed
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY).ready:
                # If we have gateway completed, build cyber core
                if not self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.CYBERNETICSCORE)
                        and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                    ):
                        await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            else:
                # If we have no gateway, build gateway
                if self.can_afford(UnitTypeId.GATEWAY) and self.already_pending(UnitTypeId.GATEWAY) == 0:
                    await self.build(UnitTypeId.GATEWAY, near=pylon)
        # Build gas near completed nexuses once we have a cybercore (does not need to be completed
        if self.structures(UnitTypeId.CYBERNETICSCORE):
            for nexus in self.townhalls.ready:
                vgs = self.vespene_geyser.closer_than(15, nexus)
                for vg in vgs:
                    if not self.can_afford(UnitTypeId.ASSIMILATOR):
                        break

                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break

                    if not self.gas_buildings or not self.gas_buildings.closer_than(1, vg):
                        worker.build_gas(vg)
                        worker.stop(queue=True)
    async def buildorder3Warpgate(self):
        #Basic build-order for a 3 warpgate push with stalkers
        # Once we have a pylon completed
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY) or self.structures(UnitTypeId.WARPGATE):
                # If we have gateway build another one
                if (len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))<=2) and self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.GATEWAY)
                        and self.already_pending(UnitTypeId.GATEWAY) <= 1
                    ):
                        await self.build(UnitTypeId.GATEWAY, near=pylon)
                # If we have a gateway completed, build a cybernetics core
                if len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))>=1 and not self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.CYBERNETICSCORE)
                        and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                    ):
                        await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
                elif(self.structures(UnitTypeId.CYBERNETICSCORE)):
                    self.warpgate_research()
            else:
                # If we have no gateway, build gateway
                if self.can_afford(UnitTypeId.GATEWAY) and self.already_pending(UnitTypeId.GATEWAY) == 0:
                    await self.build(UnitTypeId.GATEWAY, near=pylon)
        if(len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))>=2) and self.structures(UnitTypeId.CYBERNETICSCORE) and len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))<=5:
            if(self.can_afford(UnitTypeId.NEXUS) ):
                if (
                        self.can_afford(UnitTypeId.GATEWAY)
                    ):
                        await self.build(UnitTypeId.GATEWAY, near=pylon)
                        self.desiredStalkerCount +=2
        
        # Build gas near completed nexuses once we have a warpgate (does not need to be completed
        if ((self.structures(UnitTypeId.GATEWAY) or self.structures(UnitTypeId.WARPGATE)) and not self.structures(UnitTypeId.ASSIMILATOR)) or not self.firstWave:
            for nexus in self.townhalls.ready:
                vgs = self.vespene_geyser.closer_than(15, nexus)
                for vg in vgs:
                    if not self.can_afford(UnitTypeId.ASSIMILATOR):
                        break

                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break

                    if not self.gas_buildings or not self.gas_buildings.closer_than(1, vg):
                        worker.build_gas(vg)
                        worker.stop(queue=True)
    async def STPRecruitment(self):
        #builds stalkers once we have 2 warpgates
        if len(self.structures(UnitTypeId.GATEWAY).ready)+len(self.structures(UnitTypeId.WARPGATE).ready) >= 2 and len(self.units(UnitTypeId.STALKER))<self.desiredStalkerCount+3:
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                if self.can_afford(UnitTypeId.STALKER):
                    sg.train(UnitTypeId.STALKER)
            await self.warp_new_units()
    async def VRR(self):
        # If we have at least 5 void rays, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
        if self.units(UnitTypeId.VOIDRAY).amount > 5:
            for vr in self.units(UnitTypeId.VOIDRAY):
                # Activate charge ability if the void ray just attacked
                if vr.weapon_cooldown > 0:
                    vr(AbilityId.EFFECT_VOIDRAYPRISMATICALIGNMENT)
                # Choose target and attack, filter out invisible targets
                targets = (self.enemy_units | self.enemy_structures).filter(lambda unit: unit.can_be_attacked)
                if targets:
                    target = targets.closest_to(vr)
                    vr.attack(target)
                else:
                    vr.attack(self.enemy_start_locations[0])
    async def STP(self):
        # If we have at least 2 stalkers, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
        if (self.firstWave and self.units(UnitTypeId.STALKER).amount >1):
            self.firstWave = False
            for vr in self.units(UnitTypeId.STALKER):
                # Choose target and attack, filter out invisible targets
                enemies: Units = self.enemy_units | self.enemy_structures
                enemies2 = self.enemy_units.filter(lambda unit: unit.type_id in {UnitTypeId.DRONE,UnitTypeId.PROBE,UnitTypeId.PYLON})
                #targets = (self.enemy_units | self.enemy_structures).filter(lambda unit: unit.can_be_attacked)
                if enemies2:
                    target = enemies2.closest_to(vr)
                    vr.attack(target)
                else:
                    vr.attack(self.enemy_start_locations[0])
        else:
            await self.fight()

    #method to research warpgate
    def warpgate_research(self):
        if (
            self.structures(UnitTypeId.CYBERNETICSCORE).ready
            and self.can_afford(AbilityId.RESEARCH_WARPGATE)
            and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0
        ):
        #We research warp gate ! 
            ccore = self.structures(UnitTypeId.CYBERNETICSCORE).ready.first
            ccore.research(UpgradeId.WARPGATERESEARCH)

    async def warp_new_units(self):
        for warpgate in self.structures(UnitTypeId.WARPGATE).ready:
            #We take the abilities of the warpgate to retrieves the warping stalker ability
            abilities = await self.get_available_abilities(warpgate)
            #if it is not on cooldown
            if AbilityId.WARPGATETRAIN_STALKER in abilities:
                #we sort the pylons by their distance to our warp gate
                self.ordered_pylons = sorted(self.structures(UnitTypeId.PYLON).ready, key=lambda pylon: pylon.distance_to(warpgate))
                #we pick the pylon the further away from the warp gate, because why not
                pos = self.ordered_pylons[-1].position.random_on_distance(4)
                #we select the placement of the stalker we want to warp as the position of the pylon selected 
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, pos, placement_step=1)
                #if no placement  available we return error
                if placement is None:
                    print("can't place")
                    return
                #else we warp our stalker ! 
                warpgate.warp_in(UnitTypeId.STALKER, placement)
    #Functions used for evasion behaviour
    def around8(self, position, distance=1):
            p = position
            d = distance
            return self.around4(position, distance) | {
                Point2((p.x - d, p.y - d)),
                Point2((p.x - d, p.y + d)),
                Point2((p.x + d, p.y - d)),
                Point2((p.x + d, p.y + d)),
            }
    def around4(self, position, distance=1):
        p = position
        d = distance
        return {Point2((p.x - d, p.y)), Point2((p.x + d, p.y)), Point2((p.x, p.y - d)), Point2((p.x, p.y + d))}

    #Stalker behavior
    async def fight(self):
        enemies = self.enemy_units.filter(lambda unit: unit.type_id not in {})
        enemy_fighters = enemies.filter(lambda u: u.can_attack) + self.enemy_structures(
            {UnitTypeId.PHOTONCANNON}
        )
        #If not on full attack capability scatter for guerilla attacks and only attack when threatened
        if self.units(UnitTypeId.STALKER).amount >= self.desiredStalkerCount:
            self.STP_complete = True
            for stalker in self.units(UnitTypeId.STALKER).ready.idle:
                if enemy_fighters:
                    # select enemies in range
                    in_range_enemies = enemy_fighters.in_attack_range_of(stalker)
                    if in_range_enemies:
                        # prioritize workers
                        workers = in_range_enemies({UnitTypeId.DRONE, UnitTypeId.SCV, UnitTypeId.PROBE})
                        if workers:
                            in_range_enemies = workers
                        if stalker.ground_range > 1:
                            # attack if weapon not on cooldown
                            if stalker.weapon_cooldown == 0:
                                # attack enemy with lowest hp
                                lowest_hp = min(in_range_enemies, key=lambda e: (e.health + e.shield, e.tag))
                                stalker.attack(lowest_hp)
                            else:
                                #DOESN'T WORK
                                friends_in_range = self.units(UnitTypeId.STALKER).in_attack_range_of(stalker)
                                closest_enemy = in_range_enemies.closest_to(stalker)
                                distance = stalker.ground_range + stalker.radius + closest_enemy.radius
                                if (
                                    len(friends_in_range) <= len(in_range_enemies)
                                    and closest_enemy.ground_range <= stalker.ground_range
                                ):
                                    distance += 1
                                else:
                                    # if more than 5 units friends are close, use distance one shorter than range
                                    # to let other friendly units get close enough as well and not block each other
                                    if len(self.units(UnitTypeId.STALKER).closer_than(7, stalker.position)) >= 5:
                                        distance -= -1
                                stalker.move(closest_enemy.position.towards(stalker, distance))
                        else:
                            lowest_hp = min(in_range_enemies, key=lambda e: (e.health + e.shield, e.tag))
                            stalker.attack(lowest_hp)
                    else:
                        # no unit in range, go to closest
                        #stalker.move(enemy_fighters.closest_to(stalker))
                        #if(self.structures(UnitTypeId.PYLON).ready):
                        #    self.ordered_pylons = sorted(self.structures(UnitTypeId.PYLON).ready, key=lambda pylon: pylon.distance_to(self.townhalls[0]))
                        #    pos = self.ordered_pylons[-1].position.random_on_distance(4)
                        #    if((stalker.distance_to(pos)>100) or(len(self.units(UnitTypeId.STALKER).in_attack_range_of(stalker))<5)) and not stalker.is_attacking :
                        #        stalker.move(pos)
                        pass
                # no dangerous enemy at all, attack closest anything
                else:
                    stalker.attack(self.enemy_start_locations[0])
        elif self.units(UnitTypeId.STALKER).ready.amount > 0 and  self.units(UnitTypeId.STALKER).amount < self.desiredStalkerCount:
            self.STP_complete = False
            for stalker in self.units(UnitTypeId.STALKER).ready.idle:
                if enemy_fighters:
                    # select enemies in range
                    in_range_enemies = enemy_fighters.in_attack_range_of(stalker)
                    if in_range_enemies:
                        # prioritize workers
                        workers = in_range_enemies({UnitTypeId.PROBE})
                        #if workers:
                        #    in_range_enemies = workers
                        # special micro for ranged units
                        if stalker.ground_range > 1:
                            # attack if weapon not on cooldown
                            if stalker.weapon_cooldown == 0:
                                # attack enemy with lowest hp of the ones in range
                                lowest_hp = min(in_range_enemies, key=lambda e: (e.health + e.shield, e.tag))
                                stalker.attack(lowest_hp)
                            else:
                                # micro away from closest unit
                                # move further away if too many enemies are near
                                friends_in_range = self.units(UnitTypeId.STALKER).in_attack_range_of(stalker)
                                closest_enemy = in_range_enemies.closest_to(stalker)
                                distance = stalker.ground_range + stalker.radius + closest_enemy.radius
                                if (
                                    len(friends_in_range) <= len(in_range_enemies)
                                    and closest_enemy.ground_range <= stalker.ground_range
                                ):
                                    distance += 1
                                else:
                                    # if more than 5 units friends are close, use distance one shorter than range
                                    # to let other friendly units get close enough as well and not block each other
                                    if len(self.units(UnitTypeId.STALKER).closer_than(7, stalker.position)) >= 5:
                                        distance -= -1
                                stalker.move(closest_enemy.position.towards(stalker, distance))
                        else:
                            # target fire with melee units
                            lowest_hp = min(in_range_enemies, key=lambda e: (e.health + e.shield, e.tag))
                            stalker.attack(lowest_hp)
                    else:
                        # no unit in range, go to closest
                        pass
                        #stalker.move(enemy_fighters.closest_to(stalker))
    async def kite(self):
        home_location = self.start_location
        enemies: Units = self.enemy_units | self.enemy_structures
        enemies2 = self.enemy_units.filter(lambda unit: unit.type_id not in {UnitTypeId.PROBE})
        enemies_can_attack: Units = enemies2.filter(lambda unit: unit.can_attack_ground)
        for stalker in self.units(UnitTypeId.STALKER).ready:
            escape_location = stalker.position.towards(home_location, 6)
            enemyThreatsClose: Units = enemies_can_attack.filter(lambda unit: unit.distance_to(stalker) < 20)
            if stalker.shield < 4 and enemyThreatsClose:
                abilities = await self.get_available_abilities(stalker)
                if AbilityId.EFFECT_BLINK_STALKER in abilities:
                    stalker(AbilityId.EFFECT_BLINK_STALKER, escape_location)
                    continue
                else: 
                    retreatPoints: Set[Point2] = self.around8(stalker.position, distance=2) | self.around8(stalker.position, distance=4)
                    retreatPoints: Set[Point2] = {x for x in retreatPoints if self.in_pathing_grid(x)}
                    if retreatPoints:
                        closestEnemy: Unit = enemyThreatsClose.closest_to(stalker)
                        retreatPoint: Unit = closestEnemy.position.furthest(retreatPoints)
                        stalker.move(retreatPoint)
                        continue
    #gather stray units and form army
    async def groupUp(self):
        if(self.structures(UnitTypeId.PYLON).ready):
            self.ordered_pylons = sorted(self.structures(UnitTypeId.PYLON).ready, key=lambda pylon: pylon.distance_to(self.townhalls[0]))
            pos = self.ordered_pylons[-1].position.random_on_distance(4)
            for unit in self.units.filter(lambda unit: unit.type_id not in {UnitTypeId.PROBE}):
                if((unit.distance_to(pos)>100) or(len(self.units(UnitTypeId.STALKER).in_attack_range_of(unit))<5)) and not unit.is_attacking :
                    unit.move(pos)


def main():
    run_game(
        maps.get("BerlingradAIE"),
        [Bot(Race.Protoss, Brotoss()),
        #Computer(Race.Protoss, Difficulty.Hard)
        Bot(Race.Protoss, StalkerCheeseBot())
         ],
        realtime=True,
    )

if __name__ == "__main__":
    main()
