int *a, **b = &a, c = 1, d, e, f;
int main() {
	  int h = -2, i = -1;
	    unsigned long j = 18446744073709551615UL;
	     L:
	      *b = &f;
	        if (j >= 18446744073709551615UL)
			    c = 0;
		  while ((unsigned long)f <= j && h >= i)
			      *a = 1;
		    e = 1 - c;
		      j = f = ~(j - e);
		        d = ~-i;
			  h = 0;
			    int l = ~(f + d);
			      if (l)
				          goto L;
			        return 0;
}
