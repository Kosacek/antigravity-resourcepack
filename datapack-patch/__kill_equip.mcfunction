tellraw @a[tag=swPool_debug] [{"text":"reverted ball state...","color":"red"}]
execute unless data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] at @s run data modify entity @s ArmorItems set from entity @e[tag=swPool_tmprender,limit=1,sort=nearest] ArmorItems
execute unless data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] at @s run data modify entity @s Pose set from entity @e[tag=swPool_tmprender,limit=1,sort=nearest] Pose

execute if data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] at @s run data modify entity @s item set from entity @e[tag=swPool_tmprender,limit=1,sort=nearest] item
execute if data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] at @s run data modify entity @s transformation set from entity @e[tag=swPool_tmprender,limit=1,sort=nearest] transformation

# Antigravity Server: show the balls again (see __copy_unequip)
execute if data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] run data merge entity @s {view_range:1f}
execute if data storage minecraft:swpool {version:[1210]} as @e[tag=swPool_pool] on passengers on passengers run data merge entity @s {view_range:1f}

schedule function pool:classes/bot/generic/__kill_equip_delay 1t
