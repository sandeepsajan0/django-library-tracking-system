import random
rand_list = random.sample(range(1, 20), 10)

print("Random numbers: ", rand_list)

list_comprehension_below_10 = [rand_int for rand_int in rand_list if rand_int<10]

print("List comprehension: ", list_comprehension_below_10)

filter_below_10 = list(filter(lambda x:x<10, rand_list))

print("Using Filter: ", filter_below_10)