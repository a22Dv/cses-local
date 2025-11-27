n = int(input())
while (print(f"{n} ") or True) and n != 1:
  n = 3*n + 1 if n%2 == 1 else n//2