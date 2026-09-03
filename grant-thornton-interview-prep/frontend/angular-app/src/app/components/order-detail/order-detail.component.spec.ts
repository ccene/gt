import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { OrderDetailComponent } from './order-detail.component';
import { ApiService } from '../../services/api.service';
import { of, throwError } from 'rxjs';
import { Order } from '../../models/order';

describe('OrderDetailComponent', () => {
  let component: OrderDetailComponent;
  let fixture: ComponentFixture<OrderDetailComponent>;
  let apiService: ApiService;

  const mockOrder: Order = {
    id: '1',
    customerName: 'Test Customer',
    customerEmail: 'test@example.com',
    items: [{ productId: 'p1', productName: 'Product 1', quantity: 2, price: 10 }],
    status: 'pending',
    createdAt: new Date().toISOString()
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [OrderDetailComponent],
      imports: [HttpClientTestingModule],
      providers: [
        ApiService,
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: {
                get: (key: string) => key === 'id' ? '1' : null
              }
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(OrderDetailComponent);
    component = fixture.componentInstance;
    apiService = TestBed.inject(ApiService);
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display loading spinner initially', () => {
    fixture.detectChanges();
    const spinner = fixture.nativeElement.querySelector('.spinner-border');
    expect(spinner).toBeTruthy();
  });

  it('should display order details when API call succeeds', () => {
    jest.spyOn(apiService, 'getOrderById').mockReturnValue(of(mockOrder));

    fixture.detectChanges();
    component.loadOrder('1');

    fixture.detectChanges();
    const customerName = fixture.nativeElement.querySelector('p strong');
    expect(customerName.textContent).toContain('Name:');
  });

  it('should display error when API call fails', () => {
    jest.spyOn(apiService, 'getOrderById').mockReturnValue(throwError(() => new Error('Failed')));

    fixture.detectChanges();
    component.loadOrder('1');
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('.alert-danger');
    expect(alert.textContent).toContain('Failed');
  });
});
