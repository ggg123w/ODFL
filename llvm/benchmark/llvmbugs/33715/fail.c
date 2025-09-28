int a, b;

void f ()
{ 
  int d, e;
  for (b = 0; b < 23; b++)
    { 
      e = b ? 1 % b : 0;
      d = e || 4 > (5 >> e) ? 0 : 4;
      a ^= d;
    }
}