#include <stdio.h>
 
int main() {
    long long unsigned n;
    scanf_s("%llu", &n);
    for (int i = 1; i <= n; ++i) {
        long long unsigned bsize, pl, atk;
        bsize = i * i;
        pl = (bsize * (bsize - 1)) / 2;
        atk = 4 * (i - 1) * (i - 2);
        printf("%llu\n", pl - atk);
    }
}