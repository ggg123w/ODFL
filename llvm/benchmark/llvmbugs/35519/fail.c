#include<stdio.h>
int main ()
{
    unsigned int i = 0, j = 0;
    unsigned int a [10] = {0}, s [10] = {0};
    a[0] = 1;
    for (i = 0; i < 6; ++i) 
        for (j = 1; j < i; ++j) 
            a[j - 1] = s[j];
    printf("%u\n", a[0]);
    return 0;
}
