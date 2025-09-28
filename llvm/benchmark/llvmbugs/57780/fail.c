int printf(const char *, ...);

int a = 0, b = 1;
short c = 0;
long d = 0;

int main() {
  int h = 10;

i:
  if (h) {
    int j = 0;
    if (d) {
      long k = 4;
    l:
      if (b)
        goto i;
    }
    h = 0;
    for (; h < 2; ++h) {
      if (!a)
        goto l;
      c = 5;
    }
  }

  printf("%d\n", c);
}
