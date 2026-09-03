import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { OrderListComponent } from './order-list.component';
import { ApiService } from '../../services/api.service';
import { of, throwError } from 'rxjs';

describe('OrderListComponent', () => {
  let component: OrderListComponent;
  let fixture: ComponentFixture<OrderListComponent>;
  let apiService: ApiService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [OrderListComponent],
      imports: [HttpClientTestingModule],
      providers: [ApiService]
    }).compileComponents();

    fixture = TestBed.createComponent(OrderListComponent);
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

  it('should display orders when API call succeeds', () => {
    const mockOrders = [
      { id: '1', customerName: 'Test', items: [], status: 'pending', createdAt: new Date().toISOString() }
    ];
    jest.spyOn(apiService, 'getOrders').mockReturnValue(of(mockOrders));

    fixture.detectChanges();
    component.loadOrders();

    fixture.detectChanges();
    const rows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
  });

  it('should display error when API call fails', () => {
    jest.spyOn(apiService, 'getOrders').mockReturnValue(throwError(() => new Error('Failed')));

    fixture.detectChanges();
    component.loadOrders();
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('.alert-danger');
    expect(alert.textContent).toContain('Failed');
  });
});
