from .models import CartItem


def cart_count(request):
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    return {'cart_count': CartItem.objects.filter(user=request.user, product__is_sold=False).count()}
